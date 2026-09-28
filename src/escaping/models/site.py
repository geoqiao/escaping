from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..build_result import Diagnostic
from ..routes import Route, RouteRegistry
from .blog_archive import ArchivePage
from .blog_post import BlogPost
from .content import AboutPage, Idea, ProfileAbout
from .projects import Project
from .tag_taxonomy import Tag


@dataclass(frozen=True)
class SiteLink:
    name: str
    url: str


@dataclass(frozen=True)
class SiteProfile:
    avatar: str = ""
    bio: str = ""
    links: tuple[SiteLink, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CommentsMetadata:
    enabled: bool
    repo: str


@dataclass(frozen=True)
class SeoMetadata:
    google_search_console: str = ""
    social_image: str = ""
    social_image_alt: str = ""


@dataclass(frozen=True)
class SiteMetadata:
    """Theme-independent site identity from the site layer of the Config."""

    title: str
    author: str
    description: str
    language: str
    repo: str
    navigation: tuple[SiteLink, ...]
    profile: SiteProfile
    comments: CommentsMetadata
    seo: SeoMetadata


@dataclass(frozen=True)
class ExtraPage:
    """A page from ``pages.extra``; ``project`` is set for ``for_each``."""

    route: Route
    template: str
    project: Project | None = None


@dataclass(frozen=True)
class Redirect:
    """An old address, from ``redirects`` in the Config, and where it went.

    ``path`` is the decoded site path; ``url`` is its full, encoded address.
    """

    path: str
    output_path: str
    url: str
    target: Route


@dataclass(frozen=True)
class SiteModel:
    """Complete immutable build model consumed by renderer and validator."""

    metadata: SiteMetadata
    blogs: tuple[BlogPost, ...]
    archives: tuple[ArchivePage, ...]
    ideas: tuple[Idea, ...]
    about: AboutPage | ProfileAbout | None
    projects: tuple[Project, ...]
    tags: tuple[Tag, ...]
    extra_pages: tuple[ExtraPage, ...]
    routes: RouteRegistry
    build_start_time: datetime
    redirects: tuple[Redirect, ...] = field(default_factory=tuple)
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)
    skipped_issues: tuple[int, ...] = field(default_factory=tuple)

    @property
    def has_errors(self) -> bool:
        """Errors that stop publication; a Skipped Issue's errors do not."""
        return any(
            d.severity == "error" and d.issue_number not in self.skipped_issues
            for d in self.diagnostics
        )
