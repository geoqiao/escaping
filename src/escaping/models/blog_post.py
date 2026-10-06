from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..routes import Route


@dataclass(frozen=True)
class BlogTag:
    """A Blog tag as shown on one post; ``route`` is None when Tags are off."""

    name: str
    key: str
    route: Route | None

    @property
    def path(self) -> str | None:
        return self.route.canonical_path if self.route else None


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
    #: The author's Markdown, front matter removed; the Content Export writes it.
    body_markdown: str = ""

    @property
    def canonical_path(self) -> str:
        return self.route.canonical_path

    @property
    def canonical_url(self) -> str:
        return self.route.canonical_url
