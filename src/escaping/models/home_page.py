from __future__ import annotations

from dataclasses import dataclass, field

from ..routes import Route
from .blog_post import BlogTag


@dataclass(frozen=True)
class HomePostEntry:
    issue_number: int
    title: str
    description: str
    created_date: str
    detail_path: str
    tags: tuple[BlogTag, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class HomePage:
    """Home page content carrying one complete registry-created Route."""

    route: Route
    recent_posts: tuple[HomePostEntry, ...] = field(default_factory=tuple)

    @property
    def canonical_url(self) -> str:
        return self.route.canonical_url
