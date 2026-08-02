from __future__ import annotations

from dataclasses import dataclass, field

from .content import ContentRoute


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
    route: ContentRoute = field(
        default_factory=lambda: ContentRoute("/projects/", "projects/index.html")
    )

    @property
    def canonical_path(self) -> str:
        return self.route.canonical_path
