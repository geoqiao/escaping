from __future__ import annotations

from dataclasses import dataclass

from ..routes import Route
from .blog_post import BlogTag


@dataclass(frozen=True)
class ArchiveEntry:
    """One pre-resolved Blog summary in an archive page."""

    issue_number: int
    title: str
    created_date: str
    detail_path: str
    tags: tuple[BlogTag, ...]


@dataclass(frozen=True)
class ArchivePage:
    """One paginated archive page with registry-created adjacent Routes."""

    page_number: int
    total_pages: int
    route: Route
    prev_route: Route | None
    next_route: Route | None
    entries: tuple[ArchiveEntry, ...]

    @property
    def canonical_url(self) -> str:
        return self.route.canonical_url
