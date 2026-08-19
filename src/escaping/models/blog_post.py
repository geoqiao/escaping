from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..routes import Route


@dataclass(frozen=True)
class BlogTag:
    """Display name and registered canonical path for one Blog tag."""

    name: str
    path: str


@dataclass(frozen=True)
class BlogPost:
    """Compiled Blog detail page carrying its complete registered Route."""

    issue_number: int
    title: str
    slug: str
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


def blog_post_sort_key(post: BlogPost) -> tuple[datetime, int]:
    return post.published_at, post.issue_number
