from __future__ import annotations

from dataclasses import dataclass, field

from ..routes import Route


@dataclass(frozen=True)
class Project:
    slug: str
    title: str
    repository: str
    summary: str
    url: str
    featured: bool
    order: int
    stars: int | None = None
    forks: int | None = None
    language: str | None = None
    topics: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ProjectsPage:
    projects: tuple[Project, ...]
    featured: tuple[Project, ...]
    route: Route

    def top_by_stars(self, limit: int = 5) -> tuple[Project, ...]:
        """Return known-star projects first, preserving catalog order for ties."""
        ranked = sorted(
            self.projects,
            key=lambda project: (
                project.stars is None,
                -(project.stars or 0),
                project.order,
                project.slug,
            ),
        )
        return tuple(ranked[:limit])

    @property
    def canonical_path(self) -> str:
        return self.route.canonical_path

    @property
    def canonical_url(self) -> str:
        return self.route.canonical_url
