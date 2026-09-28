from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..build_result import Diagnostic
from ..routes import Route
from .blog_post import BlogPost


@dataclass(frozen=True)
class IdeaTag:
    """Display-only Idea label; it has no page, so ``path`` is None."""

    name: str
    path = None


@dataclass(frozen=True)
class Idea:
    issue_number: int
    title: str
    description: str
    created_date: str
    published_at: datetime
    updated_at: datetime
    tags: tuple[IdeaTag, ...]
    body_html: str
    route: Route

    @property
    def canonical_path(self) -> str:
        return self.route.canonical_path

    @property
    def canonical_url(self) -> str:
        return self.route.canonical_url


@dataclass(frozen=True)
class AboutPage:
    """About from an Issue. It shows no date, so ``created_date`` is empty."""

    issue_number: int
    title: str
    description: str
    body_html: str
    route: Route
    is_profile = False
    created_date = ""
    tags = ()

    @property
    def canonical_path(self) -> str:
        return self.route.canonical_path

    @property
    def canonical_url(self) -> str:
        return self.route.canonical_url


@dataclass(frozen=True)
class ProfileAbout:
    """About from the Profile when there is no About Issue.

    It has no Issue, date or tags; ``body_html`` is the bio as one paragraph.
    """

    title: str
    description: str
    body_html: str
    route: Route
    is_profile = True
    issue_number = None
    created_date = ""
    tags = ()

    @property
    def canonical_path(self) -> str:
        return self.route.canonical_path

    @property
    def canonical_url(self) -> str:
        return self.route.canonical_url


@dataclass(frozen=True)
class ContentCompilationResult:
    """Compiled content; ``skipped`` Issues are left out but do not stop the build."""

    blogs: tuple[BlogPost, ...] = field(default_factory=tuple)
    ideas: tuple[Idea, ...] = field(default_factory=tuple)
    about: AboutPage | None = None
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)
    skipped: tuple[int, ...] = field(default_factory=tuple)

    @property
    def has_errors(self) -> bool:
        return any(
            d.severity == "error" and d.issue_number not in self.skipped
            for d in self.diagnostics
        )
