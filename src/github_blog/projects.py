from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .config import ProjectCatalogEntry
from .models.projects import Project, ProjectsPage


@dataclass(frozen=True)
class ProjectEnrichment:
    stars: int | None = None
    forks: int | None = None
    language: str | None = None
    topics: tuple[str, ...] = ()


class ProjectCompiler:
    """Compile curated repository-owned project entries with optional enrichment."""

    def __init__(
        self, enrich: Callable[[str], ProjectEnrichment] | None = None
    ) -> None:
        self._enrich = enrich

    def compile(self, entries: Sequence[ProjectCatalogEntry]) -> ProjectsPage:
        projects: list[Project] = []
        for entry in sorted(entries, key=lambda value: (value.order, value.slug)):
            fallback = entry.fallback_metadata
            values = ProjectEnrichment(
                stars=fallback.stars if fallback else None,
                forks=fallback.forks if fallback else None,
                language=fallback.language if fallback else None,
                topics=tuple(fallback.topics or ()) if fallback else (),
            )
            if self._enrich is not None:
                try:
                    enriched = self._enrich(entry.repository)
                except Exception:
                    enriched = None
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
                    )
            projects.append(
                Project(
                    slug=entry.slug,
                    title=entry.title,
                    repository=entry.repository,
                    summary=entry.summary,
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
        return ProjectsPage(
            items, tuple(project for project in items if project.featured)
        )
