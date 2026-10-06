"""Content Export: published Issue Content as Markdown files.

The only output of escaping. Selection, defaults and content rules are those
of ``issue_content``. Nothing here knows a site: no address, page or look. The
files and their fields are defined in docs/contracts/content-export-v1.md.

The directory is replaced as a whole, through staging and an ownership check.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import yaml

from .build_result import BuildResult, Diagnostic
from .config import ContentSettings
from .content_validation import tag_key
from .issue_content import (
    ContentRules,
    Entry,
    IssueContent,
    IssueSource,
    compile_issues,
)
from .output_safety import OutputContainmentError
from .output_staging import OutputStagingError, OutputStagingService

#: Version of the exported files; a consumer checks it in ``manifest.json``.
EXPORT_VERSION = 1
#: Default ``--output``, relative to the Config directory.
DEFAULT_OUTPUT = "build/content"

_LINE_ENDING = re.compile(r"\r\n?")


class ContentExporter:
    """Check the directory -> fetch Issues -> compile -> write -> publish."""

    def __init__(
        self,
        settings: ContentSettings,
        *,
        config_root: Path,
        output: str,
        issues: IssueSource,
    ) -> None:
        if not config_root.is_absolute():
            raise ValueError("ContentExporter config_root must be absolute")
        self.settings = settings
        self.config_root = config_root
        self.output = output
        self.issues = issues

    def export(self) -> BuildResult:
        try:
            staging = OutputStagingService(self.output, self.config_root, "--output")
            staging.check_replaceable()
        except (OutputContainmentError, OutputStagingError) as exc:
            return _failed("OUTPUT_UNSAFE", str(exc))

        try:
            snapshots = self.issues()
        except Exception as exc:
            # Never show the exception text: client errors may echo request data.
            return _failed(
                "FETCH_FAILED",
                "could not read the Issues of the content repository "
                f"({type(exc).__name__}); check the token and repository",
            )

        content = compile_issues(
            ContentRules(
                allowed_authors=tuple(self.settings.github.allowed_authors),
                about_issue_number=self.settings.about.issue_number,
            ),
            snapshots,
        )
        diagnostics = list(content.diagnostics)
        if content.has_errors:
            return BuildResult(False, tuple(diagnostics))

        staging_dir: Path | None = None
        try:
            staging_dir = staging.create_staging_directory()
            write_export(staging_dir, content, self.settings.github.repo)
            diagnostics.extend(staging.publish(staging_dir))
            return BuildResult(True, tuple(diagnostics), content.skipped)
        except OutputStagingError as exc:
            diagnostics.append(Diagnostic("error", "PUBLISH_FAILED", str(exc)))
            if not exc.recovery_paths and staging_dir is not None:
                diagnostics.extend(staging.cleanup(staging_dir))
            return BuildResult(False, tuple(diagnostics))
        except OSError as exc:
            diagnostics.append(Diagnostic("error", "EXPORT_FAILED", str(exc)))
            if staging_dir is not None:
                diagnostics.extend(staging.cleanup(staging_dir))
            return BuildResult(False, tuple(diagnostics))


def write_export(directory: Path, content: IssueContent, repository: str) -> None:
    """Write one Markdown file per page and the manifest into ``directory``."""
    manifest: dict[str, object] = {
        "export_version": EXPORT_VERSION,
        "repository": repository,
        "blog": [
            {
                "issue_number": post.issue_number,
                "slug": post.slug,
                "path": _write(directory, f"blog/{post.slug}.md", post),
            }
            for post in content.blogs
        ],
        "ideas": [
            {
                "issue_number": idea.issue_number,
                "path": _write(directory, f"ideas/{idea.issue_number}.md", idea),
            }
            for idea in content.ideas
        ],
        "about": (
            {
                "issue_number": content.about.issue_number,
                "path": _write(directory, "about.md", content.about),
            }
            if content.about
            else None
        ),
        "skipped_issues": list(content.skipped),
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _write(directory: Path, path: str, page: Entry) -> str:
    head = yaml.safe_dump(
        _metadata(page), allow_unicode=True, sort_keys=False, width=float("inf")
    )
    body = _LINE_ENDING.sub("\n", page.body_markdown).strip("\n")
    target = directory / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"---\n{head}---\n\n{body}\n", encoding="utf-8", newline="\n")
    return path


def _metadata(page: Entry) -> dict[str, object]:
    """Front matter of one exported file, every value resolved."""
    data: dict[str, object] = {
        "issue_number": page.issue_number,
        "type": page.type,
        "title": page.title,
    }
    if page.type == "blog":
        data["slug"] = page.slug
    data["description"] = page.description
    if page.type == "about":  # About shows no date and has no tags
        return data
    data |= {
        "created_date": page.created_date,
        "update_date": page.update_date,
        "published_at": _utc(page.published_at),
        "updated_at": _utc(page.updated_at),
        "tags": [{"name": name, "key": tag_key(name)} for name in page.tags],
    }
    return data


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _failed(code: str, message: str) -> BuildResult:
    return BuildResult(False, (Diagnostic("error", code, message),))
