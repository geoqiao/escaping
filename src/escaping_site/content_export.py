"""Content Export: published Issue Content as Markdown files.

For a site built with another tool. Selection, defaults and content rules are
the Content Compiler's, so an Issue is exported exactly when ``escaping-site build``
would publish it. No Theme is loaded and no page is rendered; the files and
their fields are defined in docs/contracts/content-export-v1.md.

The directory is replaced as a whole through the same staging and ownership
checks as a built site.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import yaml

from .build_result import BuildResult, Diagnostic
from .config import Settings
from .content_compiler import ContentCompiler
from .content_validation import tag_key
from .models.blog_post import BlogPost, BlogTag
from .models.content import AboutPage, ContentCompilationResult, Idea, IdeaTag
from .output_safety import OutputContainmentError
from .output_staging import OutputStagingError, OutputStagingService
from .routes import RouteRegistry
from .site_builder import register_fixed_routes
from .site_compiler import IssueSource

#: Version of the exported files; a consumer checks it in ``manifest.json``.
EXPORT_VERSION = 1
#: Default ``--output``, relative to the Config directory.
DEFAULT_OUTPUT = "build/content"

_LINE_ENDING = re.compile(r"\r\n?")


class ContentExporter:
    """Check the directory -> fetch Issues -> compile -> write -> publish."""

    def __init__(
        self,
        settings: Settings,
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
            self._check_apart_from_site(staging.output)
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

        routes = RouteRegistry(
            str(self.settings.site.url), self.settings.pages.sections()
        )
        register_fixed_routes(routes)
        content = ContentCompiler(self.settings, route_registry=routes).compile(
            snapshots
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

    def _check_apart_from_site(self, output: Path) -> None:
        site = (self.config_root / self.settings.paths.output).resolve()
        if output.is_relative_to(site) or site.is_relative_to(output):
            raise OutputStagingError(
                f"--output and paths.output overlap ({output} and {site}); "
                "a build or an export would delete the other's files"
            )


def write_export(
    directory: Path, content: ContentCompilationResult, repository: str
) -> None:
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


def _write(directory: Path, path: str, page: BlogPost | Idea | AboutPage) -> str:
    head = yaml.safe_dump(
        _metadata(page), allow_unicode=True, sort_keys=False, width=float("inf")
    )
    body = _LINE_ENDING.sub("\n", page.body_markdown).strip("\n")
    target = directory / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"---\n{head}---\n\n{body}\n", encoding="utf-8", newline="\n")
    return path


def _metadata(page: BlogPost | Idea | AboutPage) -> dict[str, object]:
    """Front matter of one exported file, every value resolved."""
    if isinstance(page, AboutPage):
        return {
            "issue_number": page.issue_number,
            "type": "about",
            "title": page.title,
            "description": page.description,
        }
    data: dict[str, object] = {
        "issue_number": page.issue_number,
        "type": "blog" if isinstance(page, BlogPost) else "idea",
        "title": page.title,
    }
    if isinstance(page, BlogPost):
        data["slug"] = page.slug
    data |= {
        "description": page.description,
        "created_date": page.created_date,
        "published_at": _utc(page.published_at),
        "updated_at": _utc(page.updated_at),
        "tags": [_tag(tag) for tag in page.tags],
    }
    return data


def _tag(tag: BlogTag | IdeaTag) -> dict[str, str]:
    return {"name": tag.name, "key": tag_key(tag.name)}


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _failed(code: str, message: str) -> BuildResult:
    return BuildResult(False, (Diagnostic("error", code, message),))
