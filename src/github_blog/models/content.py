from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..build_result import Diagnostic
from .blog_post import BlogPost, BlogTag
from .home_page import HomeProfile


@dataclass(frozen=True)
class ContentRoute:
    canonical_path: str
    output_path: str


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
    canonical_path: str
    canonical_url: str = ""

    @property
    def route(self) -> ContentRoute:
        return ContentRoute(
            canonical_path=self.canonical_path,
            output_path=f"ideas/{self.issue_number}/index.html",
        )


@dataclass(frozen=True)
class AboutPage:
    issue_number: int
    title: str
    description: str
    body_html: str
    canonical_path: str
    profile: HomeProfile
    canonical_url: str = ""

    @property
    def route(self) -> ContentRoute:
        return ContentRoute(self.canonical_path, "about/index.html")


@dataclass(frozen=True)
class ContentCompilationResult:
    blogs: tuple[BlogPost, ...] = field(default_factory=tuple)
    ideas: tuple[Idea, ...] = field(default_factory=tuple)
    about: AboutPage | None = None
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)

    @property
    def has_errors(self) -> bool:
        return any(d.severity == "error" for d in self.diagnostics)
