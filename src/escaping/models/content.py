from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..build_result import Diagnostic
from ..routes import Route
from .blog_post import BlogPost, BlogTag


@dataclass(frozen=True)
class Idea:
    issue_number: int
    title: str
    description: str
    created_date: str
    published_at: datetime
    updated_at: datetime
    tags: tuple[BlogTag, ...]
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
    issue_number: int
    title: str
    description: str
    body_html: str
    route: Route

    @property
    def canonical_path(self) -> str:
        return self.route.canonical_path

    @property
    def canonical_url(self) -> str:
        return self.route.canonical_url


@dataclass(frozen=True)
class ContentCompilationResult:
    blogs: tuple[BlogPost, ...] = field(default_factory=tuple)
    ideas: tuple[Idea, ...] = field(default_factory=tuple)
    about: AboutPage | None = None
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)

    @property
    def has_errors(self) -> bool:
        return any(d.severity == "error" for d in self.diagnostics)
