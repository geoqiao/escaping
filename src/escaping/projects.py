from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .build_result import Diagnostic
from .config import ProjectCatalogEntry
from .models.projects import Project, ProjectCompilationResult, ProjectsPage
from .routes import Route


@dataclass(frozen=True)
class ProjectEnrichment:
    stars: int | None = None
    forks: int | None = None
    language: str | None = None
    topics: tuple[str, ...] = ()
    name: str | None = None
    description: str | None = None


class ProjectCompiler:
    """Compile curated repository-owned project entries with optional enrichment."""

    def __init__(
        self, enrich: Callable[[str], ProjectEnrichment] | None = None
    ) -> None:
        self._enrich = enrich

    def compile(
        self, entries: Sequence[ProjectCatalogEntry], *, route: Route
    ) -> ProjectCompilationResult:
        projects: list[Project] = []
        diagnostics: list[Diagnostic] = []
        seen: set[str] = set()
        enrichment: dict[str, ProjectEnrichment | None] = {}
        for entry in sorted(entries, key=lambda value: (value.order, value.slug)):
            if entry.slug in seen:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "PROJECT_KEY_DUPLICATE",
                        "Duplicate project catalog key",
                        field=f"projects.{entry.slug}",
                    )
                )
            seen.add(entry.slug)
            fallback = entry.fallback_metadata
            values = ProjectEnrichment(
                stars=fallback.stars if fallback else None,
                forks=fallback.forks if fallback else None,
                language=fallback.language if fallback else None,
                topics=tuple(fallback.topics or ()) if fallback else (),
            )
            if self._enrich is not None:
                try:
                    key = entry.repository.casefold()
                    if key not in enrichment:
                        enrichment[key] = self._enrich(entry.repository)
                    enriched = enrichment[key]
                except Exception:
                    enrichment[entry.repository.casefold()] = None
                    enriched = None
                if enriched is None:
                    outcome = (
                        "configured fallback metadata was used"
                        if fallback is not None
                        else "metadata remains unavailable"
                    )
                    diagnostics.append(
                        Diagnostic(
                            "warning",
                            "PROJECT_ENRICHMENT_FAILED",
                            f"Project {entry.repository} metadata enrichment failed; "
                            f"{outcome}.",
                            field=f"projects.{entry.slug}",
                        )
                    )
                if enriched is not None:
                    values = ProjectEnrichment(
                        stars=enriched.stars
                        if enriched.stars is not None
                        else values.stars,
                        forks=enriched.forks
                        if enriched.forks is not None
                        else values.forks,
                        language=enriched.language or values.language,
                        topics=enriched.topics or values.topics,
                        name=enriched.name,
                        description=enriched.description,
                    )
            projects.append(
                Project(
                    slug=entry.slug,
                    title=(
                        entry.title
                        if "title" in entry.model_fields_set
                        else values.name or entry.title
                    ),
                    repository=entry.repository,
                    summary=(
                        entry.summary
                        if "summary" in entry.model_fields_set
                        else values.description or entry.summary
                    ),
                    url=f"https://github.com/{entry.repository}",
                    featured=entry.featured,
                    order=entry.order,
                    stars=values.stars,
                    forks=values.forks,
                    language=values.language,
                    topics=values.topics,
                )
            )
        items = tuple(projects)
        page = ProjectsPage(
            items, tuple(project for project in items if project.featured), route
        )
        return ProjectCompilationResult(page, tuple(diagnostics))
