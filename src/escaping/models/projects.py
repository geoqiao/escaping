from __future__ import annotations

from dataclasses import dataclass, field

from ..build_result import Diagnostic
from ..routes import Route


@dataclass(frozen=True)
class ProjectLink:
    name: str
    url: str


@dataclass(frozen=True)
class Project:
    """A curated project. ``url`` is its website, else its repository.

    ``page`` is the Route of the Theme's detail page when the Theme declares
    one with ``for_each: projects``.
    """

    slug: str
    title: str
    repository: str
    summary: str
    url: str
    featured: bool
    order: int
    website: str = ""
    stars: int | None = None
    forks: int | None = None
    language: str | None = None
    topics: tuple[str, ...] = field(default_factory=tuple)
    image: str = ""
    links: tuple[ProjectLink, ...] = field(default_factory=tuple)
    page: Route | None = None

    @property
    def repository_url(self) -> str:
        return f"https://github.com/{self.repository}" if self.repository else ""


@dataclass(frozen=True)
class ProjectCompilationResult:
    projects: tuple[Project, ...] = field(default_factory=tuple)
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)
