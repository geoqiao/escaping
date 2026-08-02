from __future__ import annotations

from dataclasses import dataclass, field

from ..atom_feed import AtomFeed
from ..build_result import Diagnostic
from ..routes import RouteRegistry
from .blog_archive import ArchivePage
from .blog_post import BlogPost
from .content import AboutPage, Idea
from .home_page import HomePage
from .projects import ProjectsPage
from .tag_taxonomy import TagArchive, TagsIndex


@dataclass(frozen=True)
class SiteModel:
    """Complete immutable build model consumed by the strict renderer."""

    home: HomePage
    blogs: tuple[BlogPost, ...]
    archives: tuple[ArchivePage, ...]
    ideas: tuple[Idea, ...]
    about: AboutPage | None
    projects: ProjectsPage
    tags: TagsIndex
    tag_archives: tuple[TagArchive, ...]
    feed: AtomFeed
    routes: RouteRegistry
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)

    @property
    def has_errors(self) -> bool:
        return any(d.severity == "error" for d in self.diagnostics)
