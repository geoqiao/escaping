from __future__ import annotations

from dataclasses import dataclass, field

from ..build_result import Diagnostic
from ..routes import Route, RouteRegistry
from .atom_feed import AtomFeed
from .blog_archive import ArchivePage
from .blog_post import BlogPost
from .content import AboutPage, Idea
from .home_page import HomePage
from .projects import ProjectsPage
from .tag_taxonomy import TagArchive, TagsIndex


@dataclass(frozen=True)
class SiteLink:
    name: str
    url: str


@dataclass(frozen=True)
class SiteProfile:
    avatar: str = ""
    tagline: str = ""
    bio: str = ""
    links: tuple[SiteLink, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class BrandingMetadata:
    show_powered_by: bool
    powered_by_text: str
    powered_by_url: str
    source_link_url: str


@dataclass(frozen=True)
class CommentsMetadata:
    repo: str
    theme: str
    theme_mode: str


@dataclass(frozen=True)
class ThemeMetadata:
    name: str
    asset_path: str
    favicon_url: str


@dataclass(frozen=True)
class SiteMetadata:
    """All immutable site identity and shared rendering data."""

    title: str
    author: str
    description: str
    language: str
    github_name: str
    github_repo: str
    navigation: tuple[SiteLink, ...]
    thesis: tuple[str, ...]
    profile: SiteProfile
    branding: BrandingMetadata
    comments: CommentsMetadata
    google_search_verification: str
    theme: ThemeMetadata


@dataclass(frozen=True)
class IdeasPage:
    route: Route
    ideas: tuple[Idea, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SiteModel:
    """Complete immutable build model consumed by renderer and validator."""

    metadata: SiteMetadata
    home: HomePage
    blogs: tuple[BlogPost, ...]
    archives: tuple[ArchivePage, ...]
    ideas_page: IdeasPage
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
