from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast

import structlog
from jinja2 import TemplateError, TemplateSyntaxError

from .artifact_validation import SiteArtifactValidator
from .build_result import BuildResult, Diagnostic
from .config import Settings
from .content_compiler import ContentCompiler
from .models.issue_snapshot import IssueSnapshot
from .output_safety import OutputContainmentError
from .output_staging import OutputStagingError, OutputStagingService
from .projects import ProjectCompiler, ProjectEnrichment
from .routes import RouteRegistry
from .services.github_service import GitHubService
from .services.render_service import RenderService
from .site_builder import SiteBuilder
from .theme import ThemeLoader

logger = structlog.get_logger()


class _GitHubRepository(Protocol):
    stargazers_count: int
    forks_count: int
    language: str | None

    def get_topics(self) -> list[str]: ...


class _GitHubSource(Protocol):
    def get_repo(self, name: str) -> object: ...

    def fetch_issue_snapshots(self, repo: object) -> list[IssueSnapshot]: ...


class SiteCompiler:
    """Strict one-way Site Compiler: GitHub snapshots to validated artifacts."""

    def __init__(
        self,
        token: str,
        repo_name: str,
        settings: Settings,
        *,
        config_root: Path,
        github_service: _GitHubSource | None = None,
        output_staging: OutputStagingService | None = None,
        project_enricher: Callable[[str], ProjectEnrichment] | None = None,
    ) -> None:
        self.github: _GitHubSource = cast(
            _GitHubSource, github_service or GitHubService(token)
        )
        self.repo_name = repo_name
        self.settings = settings
        if not config_root.is_absolute():
            raise ValueError("SiteCompiler config_root must be absolute")
        self.config_root = config_root
        self.output_staging = output_staging
        self.project_enricher = project_enricher

    def generate(self) -> BuildResult:
        build_start = datetime.now(UTC)
        diagnostics: list[Diagnostic] = []
        try:
            repository = self.github.get_repo(self.repo_name)
            snapshots = self.github.fetch_issue_snapshots(repository)
        except Exception as exc:
            logger.exception("fetch_failed")
            return BuildResult(
                False,
                (
                    Diagnostic(
                        "error",
                        "FETCH_FAILED",
                        f"Failed to fetch Issue snapshots: {exc}",
                    ),
                ),
            )

        routes = RouteRegistry(str(self.settings.site.url))
        content = ContentCompiler(self.settings, route_registry=routes).compile(
            snapshots
        )
        projects = ProjectCompiler(
            self.project_enricher or self._github_project_enricher
        ).compile(self.settings.projects, route=routes.projects())
        site = SiteBuilder(self.settings, route_registry=routes).build(
            content, projects, build_start_time=build_start
        )
        diagnostics.extend(site.diagnostics)
        if site.has_errors:
            return BuildResult(False, tuple(diagnostics))

        try:
            staging = self.output_staging or OutputStagingService(
                self.settings.paths.output, self.config_root
            )
        except OutputContainmentError as exc:
            return BuildResult(
                False,
                (
                    *diagnostics,
                    Diagnostic("error", "OUTPUT_CONTAINMENT_FAILED", str(exc)),
                ),
            )

        staging_dir: Path | None = None
        try:
            staging_dir = staging.create_staging_directory()
            theme = ThemeLoader(self.config_root).load(self.settings.theme)
            renderer = RenderService(theme)
            renderer.copy_theme_assets(staging_dir)
            artifacts = renderer.render_site(site)
            self._write_artifacts(staging_dir, artifacts)
            artifact_diagnostics = SiteArtifactValidator(site).validate(staging_dir)
            diagnostics.extend(artifact_diagnostics)
            if any(d.severity == "error" for d in artifact_diagnostics):
                return self._fail_staging(staging, staging_dir, diagnostics)
            diagnostics.extend(staging.publish(staging_dir))
            return BuildResult(True, tuple(diagnostics))
        except TemplateError as exc:
            logger.exception("template_render_failed")
            diagnostics.append(
                Diagnostic(
                    "error",
                    "TEMPLATE_RENDER_FAILED",
                    self._template_error_message(exc),
                )
            )
            return self._fail_staging(staging, staging_dir, diagnostics)
        except (OSError, OutputStagingError, ValueError, RuntimeError) as exc:
            logger.exception("strict_build_failed")
            diagnostics.append(Diagnostic("error", "BUILD_FAILED", str(exc)))
            if isinstance(exc, OutputStagingError) and exc.recovery_paths:
                return BuildResult(False, tuple(diagnostics))
            return self._fail_staging(staging, staging_dir, diagnostics)

    def _github_project_enricher(self, repository_name: str) -> ProjectEnrichment:
        repository = cast(_GitHubRepository, self.github.get_repo(repository_name))
        topics = tuple(repository.get_topics())
        return ProjectEnrichment(
            stars=repository.stargazers_count,
            forks=repository.forks_count,
            language=repository.language,
            topics=topics,
        )

    @staticmethod
    def _write_artifacts(output_dir: Path, artifacts: dict[str, str]) -> None:
        for relative_path, content in artifacts.items():
            path = Path(relative_path)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"unsafe artifact output path: {relative_path}")
            target = output_dir / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    @staticmethod
    def _template_error_message(exc: TemplateError) -> str:
        message = str(exc)
        if isinstance(exc, TemplateSyntaxError):
            template = exc.name or "<unknown>"
            line = exc.lineno or "unknown"
            return f"{message} (template={template} line={line})"
        return message

    @staticmethod
    def _fail_staging(
        staging: OutputStagingService,
        staging_dir: Path | None,
        diagnostics: list[Diagnostic],
    ) -> BuildResult:
        if staging_dir is not None:
            try:
                diagnostics.extend(staging.cleanup(staging_dir))
            except Exception as exc:
                diagnostics.append(Diagnostic("error", "CLEANUP_FAILED", str(exc)))
        return BuildResult(False, tuple(diagnostics))


def token_from_settings(settings: Settings) -> str | None:
    """Read the configured token variable without hard-coding its name."""
    return os.environ.get(settings.security.token_env)
