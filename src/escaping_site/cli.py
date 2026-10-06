"""Command line: ``escaping-site export``.

Exit status: 0 exported, 1 failed (nothing written), 2 exported but some
Issues were skipped because of their own errors.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .build_result import BuildResult, Diagnostic
from .config import ConfigError, read_content_overrides, security_from_config
from .content_export import DEFAULT_OUTPUT, ContentExporter
from .content_inputs import resolve_content_settings
from .issue_content import IssueSource
from .models.issue_snapshot import IssueSnapshot
from .services.github_service import GitHubService, read_issues_json

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_SKIPPED = 2


def run_cli(argv: Sequence[str] | None = None) -> None:
    sys.exit(main(argv))


def main(argv: Sequence[str] | None = None) -> int:
    return _export(_parser().parse_args(argv))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="escaping-site",
        description="Turn the published GitHub Issues of a repository into "
        "Markdown files for a site to render.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser(
        "export", help="write the published Issues as Markdown files"
    )
    export.add_argument(
        "--config", type=Path, default=Path("config.yaml"), help="Config file"
    )
    export.add_argument(
        "--issues-json",
        type=Path,
        help="read Issues from this file instead of GitHub "
        "(gh api --paginate --slurp 'repos/OWNER/REPO/issues?state=all&per_page=100')",
    )
    export.add_argument(
        "--repo", help="content repository (owner/name); overrides github.repo"
    )
    export.add_argument(
        "--token-env",
        metavar="NAME",
        help="environment variable holding the GitHub token; "
        "overrides security.token_env",
    )
    export.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="directory to replace with the export, relative to the Config "
        f"directory (default: {DEFAULT_OUTPUT})",
    )
    return parser


def _sources(
    ns: argparse.Namespace, overrides: dict[str, Any]
) -> tuple[GitHubService | None, list[IssueSnapshot] | None]:
    """The GitHub client, when there is a token, and the Issues of --issues-json."""
    token_env = ns.token_env or security_from_config(overrides).token_env
    token = os.environ.get(token_env)
    snapshots = _read_issues(ns.issues_json)
    if not token and snapshots is None:
        raise ValueError(
            f"set the {token_env} environment variable to a GitHub token, "
            "or pass --issues-json"
        )
    return (GitHubService(token) if token else None), snapshots


def _export(ns: argparse.Namespace) -> int:
    report = _Reporter()
    config_path = ns.config.expanduser().absolute()
    try:
        overrides = read_content_overrides(config_path)
        github, snapshots = _sources(ns, overrides)
        repository = ns.repo
        if repository is None and os.environ.get("GITHUB_ACTIONS") == "true":
            # On GitHub Actions the content is this repository's unless named.
            configured = "repo" in overrides.get("github", {})
            repository = None if configured else os.environ.get("GITHUB_REPOSITORY")
        settings = resolve_content_settings(
            overrides, repository=repository, github_service=github
        )
    except ConfigError as exc:
        report.fail(exc.problems)
        return EXIT_FAILED
    except (OSError, ValueError) as exc:
        report.fail([str(exc)])
        return EXIT_FAILED
    report.repo = settings.github.repo
    result = ContentExporter(
        settings,
        config_root=config_path.parent,
        output=ns.output,
        issues=_issue_source(github, settings.github.repo, snapshots),
    ).export()
    report.result(
        result,
        (),
        done=f"Exported {ns.output.rstrip('/')}/.",
        failed="Export failed; the previous export was left unchanged.",
    )
    if not result.success:
        return EXIT_FAILED
    report.outputs(
        output=str((config_path.parent / ns.output).resolve()),
        skipped_issues=",".join(map(str, result.skipped_issues)),
    )
    return EXIT_SKIPPED if result.skipped_issues else EXIT_OK


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


class _Reporter:
    """Plain lines on stderr; annotations and a job summary on GitHub Actions."""

    def __init__(self) -> None:
        self.actions = os.environ.get("GITHUB_ACTIONS") == "true"
        self.summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        self.output_path = os.environ.get("GITHUB_OUTPUT")
        self.repo = ""

    def outputs(self, **values: str) -> None:
        """Step outputs for a workflow, such as the Issues that were skipped."""
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
            failed="Nothing was exported.",
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
