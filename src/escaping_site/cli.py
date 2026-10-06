"""Command line: ``escaping-site build`` (the default), ``escaping-site export`` and
``escaping-site theme check``.

Exit status: 0 published, 1 failed (nothing published), 2 published but some
Issues were skipped because of their own errors.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .build_result import BuildResult, Diagnostic
from .config import (
    ConfigError,
    PlatformContext,
    Settings,
    read_config_overrides,
    read_platform_context,
    security_from_config,
)
from .content_export import DEFAULT_OUTPUT, ContentExporter
from .models.issue_snapshot import IssueSnapshot
from .services.github_service import (
    GitHubService,
    PagesNotReadyError,
    read_issues_json,
)
from .site_compiler import IssueSource, SiteCompiler, check_theme
from .site_inputs import resolve_settings

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_SKIPPED = 2


def run_cli(argv: Sequence[str] | None = None) -> None:
    # Progress lines, such as the commit of a downloaded Theme, go to stderr.
    logging.basicConfig(format="%(message)s")
    logging.getLogger("escaping_site").setLevel(logging.INFO)
    sys.exit(main(argv))


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or (args[0].startswith("-") and args[0] not in ("-h", "--help")):
        args.insert(0, "build")
    ns = _parser().parse_args(args)
    if ns.command == "theme":
        return _theme_check(ns)
    if ns.command == "export":
        return _export(ns)
    return _build(ns)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="escaping-site", description="Build a website from GitHub Issues."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="build and publish the site (default)")
    _common(build)
    _source(build)
    export = commands.add_parser(
        "export",
        help="write the published Issues as Markdown files, "
        "for a site built with another tool",
    )
    _common(export)
    _source(export)
    export.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="directory to replace with the export, relative to the Config "
        f"directory (default: {DEFAULT_OUTPUT})",
    )
    theme = commands.add_parser("theme", help="Theme tools")
    theme_commands = theme.add_subparsers(dest="theme_command", required=True)
    check = theme_commands.add_parser(
        "check",
        help="render the site with sample content and report Theme problems",
    )
    _common(check)
    return parser


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config", type=Path, default=Path("config.yaml"), help="site Config file"
    )
    parser.add_argument(
        "--issues-json",
        type=Path,
        help="read Issues from this file instead of GitHub "
        "(gh api --paginate --slurp 'repos/OWNER/REPO/issues?state=all&per_page=100')",
    )


def _source(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--repo", help="content repository (owner/name); overrides github.repo"
    )
    parser.add_argument(
        "--context",
        type=Path,
        help="JSON with the repository and Pages URL; on GitHub Actions the "
        "command reads them itself when the Config leaves them out",
    )
    parser.add_argument(
        "--token-env",
        metavar="NAME",
        help="environment variable holding the GitHub token; "
        "overrides security.token_env",
    )


@dataclass(frozen=True)
class _Inputs:
    """What a build and an export both read before they start."""

    settings: Settings
    config_root: Path
    github: GitHubService | None
    issues: IssueSource
    diagnostics: tuple[Diagnostic, ...]


def _inputs(ns: argparse.Namespace, report: _Reporter) -> _Inputs | None:
    config_path = ns.config.expanduser().absolute()
    try:
        overrides = read_config_overrides(config_path)
        context = read_platform_context(ns.context) if ns.context else None
        token_env = ns.token_env or security_from_config(overrides).token_env
        token = os.environ.get(token_env)
        snapshots = _read_issues(ns.issues_json)
        if not token and snapshots is None:
            report.fail(
                [
                    f"set the {token_env} environment variable to a GitHub token, "
                    "or pass --issues-json"
                ]
            )
            return None
        github = GitHubService(token) if token else None
        if context is None and github is not None:
            context = _actions_context(overrides, github)
        settings, input_diagnostics = resolve_settings(
            overrides,
            context=context,
            github_service=github,
            repository_override=ns.repo,
        )
    except ConfigError as exc:
        report.fail(exc.problems)
        return None
    except (OSError, ValueError) as exc:
        report.fail([str(exc)])
        return None
    report.repo = settings.github.repo
    return _Inputs(
        settings,
        config_path.parent,
        github,
        _issue_source(github, settings.github.repo, snapshots),
        input_diagnostics,
    )


def _actions_context(
    overrides: dict[str, Any], github: GitHubService
) -> PlatformContext | None:
    """On GitHub Actions, read what the Config leaves out from the repository.

    A Config with both ``github.repo`` and ``site.url`` needs nothing, so a site
    published elsewhere is never asked about GitHub Pages.
    """
    repository = os.environ.get("GITHUB_REPOSITORY")
    if os.environ.get("GITHUB_ACTIONS") != "true" or not repository:
        return None
    if "repo" in overrides.get("github", {}) and "url" in overrides.get("site", {}):
        return None
    try:
        return github.fetch_platform_context(repository)
    except PagesNotReadyError:
        raise
    except Exception as exc:
        # Never show the exception text: client errors may echo request data.
        raise ValueError(
            "could not read the repository and its Pages settings from GitHub "
            f"({type(exc).__name__}); check the token, or set github.repo and "
            "site.url in the Config"
        ) from None


def _build(ns: argparse.Namespace) -> int:
    report = _Reporter()
    inputs = _inputs(ns, report)
    if inputs is None:
        return EXIT_FAILED
    settings, github = inputs.settings, inputs.github
    result = SiteCompiler(
        settings,
        config_root=inputs.config_root,
        issues=inputs.issues,
        project_enricher=github.fetch_project_enrichment if github else None,
    ).generate()
    report.result(
        result,
        inputs.diagnostics,
        done=f"Published {settings.paths.output}/.",
        failed="Build failed; the previous output was left unchanged.",
    )
    return _finish(
        report, result, (inputs.config_root / settings.paths.output).resolve()
    )


def _export(ns: argparse.Namespace) -> int:
    report = _Reporter()
    inputs = _inputs(ns, report)
    if inputs is None:
        return EXIT_FAILED
    result = ContentExporter(
        inputs.settings,
        config_root=inputs.config_root,
        output=ns.output,
        issues=inputs.issues,
    ).export()
    report.result(
        result,
        inputs.diagnostics,
        done=f"Exported {ns.output.rstrip('/')}/.",
        failed="Export failed; the previous export was left unchanged.",
    )
    return _finish(report, result, (inputs.config_root / ns.output).resolve())


def _finish(report: _Reporter, result: BuildResult, output: Path) -> int:
    if not result.success:
        return EXIT_FAILED
    report.outputs(
        output=str(output),
        skipped_issues=",".join(map(str, result.skipped_issues)),
    )
    return EXIT_SKIPPED if result.skipped_issues else EXIT_OK


def _theme_check(ns: argparse.Namespace) -> int:
    report = _Reporter()
    config_path = ns.config.expanduser().absolute()
    try:
        overrides = read_config_overrides(config_path)
        snapshots = _read_issues(ns.issues_json)
        settings, _ = resolve_settings(_with_placeholders(overrides))
    except ConfigError as exc:
        report.fail(exc.problems)
        return EXIT_FAILED
    except (OSError, ValueError) as exc:
        report.fail([str(exc)])
        return EXIT_FAILED
    result = check_theme(settings, config_root=config_path.parent, snapshots=snapshots)
    report.result(
        result,
        (),
        done=f"Theme {settings.theme.use} renders every page.",
        failed="Theme check failed.",
    )
    return EXIT_OK if result.success else EXIT_FAILED


def _issue_source(
    github: GitHubService | None,
    repo: str,
    snapshots: list[IssueSnapshot] | None,
) -> IssueSource:
    if snapshots is not None:
        return lambda: snapshots
    if github is None:
        raise ValueError("a GitHub token or --issues-json is required")
    client = github
    return lambda: client.fetch_issue_snapshots(client.get_repo(repo))


def _read_issues(path: Path | None) -> list[IssueSnapshot] | None:
    return read_issues_json(path.expanduser()) if path is not None else None


def _with_placeholders(overrides: dict[str, Any]) -> dict[str, Any]:
    """Fill identity fields a real build reads from GitHub; the check is offline."""
    data = deepcopy(overrides)
    github = data.setdefault("github", {})
    github.setdefault("repo", "example/site")
    github.setdefault("allowed_authors", ["example"])
    site = data.setdefault("site", {})
    site.setdefault("url", "https://example.com/")
    for key, value in (
        ("title", "Example"),
        ("author", "Example Author"),
        ("description", "An example site."),
    ):
        site.setdefault(key, value)
    profile = data.setdefault("profile", {})
    profile.setdefault("avatar", "")
    profile.setdefault("bio", "")
    return data


class _Reporter:
    """Plain lines on stderr; annotations and a job summary on GitHub Actions."""

    def __init__(self) -> None:
        self.actions = os.environ.get("GITHUB_ACTIONS") == "true"
        self.summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        self.output_path = os.environ.get("GITHUB_OUTPUT")
        self.repo = ""

    def outputs(self, **values: str) -> None:
        """Step outputs for the Action, e.g. the directory to upload."""
        if not self.output_path:
            return
        if any("\n" in value or "\r" in value for value in values.values()):
            raise ValueError("a step output cannot contain a line break")
        with Path(self.output_path).open("a", encoding="utf-8") as file:
            for name, value in values.items():
                file.write(f"{name.replace('_', '-')}={value}\n")

    def fail(self, problems: Sequence[str]) -> None:
        self.result(
            BuildResult(
                False, tuple(Diagnostic("error", "CONFIG_INVALID", p) for p in problems)
            ),
            (),
            done="",
            failed="Nothing was built.",
        )

    def result(
        self,
        result: BuildResult,
        extra: Sequence[Diagnostic],
        *,
        done: str,
        failed: str,
    ) -> None:
        diagnostics = (*extra, *result.diagnostics)
        for diagnostic in diagnostics:
            print(f"{diagnostic.severity}: {diagnostic.message}", file=sys.stderr)
            if self.actions:
                command = "error" if diagnostic.severity == "error" else "warning"
                print(
                    f"::{command} title={_escape(diagnostic.code, True)}::"
                    f"{_escape(diagnostic.message, False)}"
                )
        headline = done if result.success else failed
        if result.success and result.skipped_issues:
            numbers = ", ".join(f"#{n}" for n in result.skipped_issues)
            headline += f" Skipped Issues {numbers}; fix the errors above."
        print(headline, file=sys.stderr)
        if self.summary_path:
            self._write_summary(headline, diagnostics)

    def _write_summary(self, headline: str, diagnostics: Sequence[Diagnostic]) -> None:
        lines = ["## escaping", "", headline, ""]
        if diagnostics:
            lines += ["| | Issue | Problem |", "| --- | --- | --- |"]
            for d in diagnostics[:100]:
                mark = "❌" if d.severity == "error" else "⚠️"
                issue = (
                    f"[#{d.issue_number}](https://github.com/{self.repo}/issues/"
                    f"{d.issue_number})"
                    if d.issue_number is not None and self.repo
                    else ""
                )
                message = d.message.replace("|", "\\|").replace("\n", " ")
                lines.append(f"| {mark} | {issue} | {message} |")
        try:
            with Path(self.summary_path or "").open("a", encoding="utf-8") as file:
                file.write("\n".join(lines) + "\n")
        except OSError:
            print("warning: could not write the job summary", file=sys.stderr)


def _escape(value: str, is_property: bool) -> str:
    value = value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    if is_property:
        value = value.replace(":", "%3A").replace(",", "%2C")
    return value
