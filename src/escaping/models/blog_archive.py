from __future__ import annotations

from dataclasses import dataclass

from ..routes import Route
from .blog_post import BlogPost


@dataclass(frozen=True)
class ArchivePage:
    """One page of the Blog archive, newest first, with adjacent page Routes."""

    page_number: int
    total_pages: int
    route: Route
    prev_route: Route | None
    next_route: Route | None
    posts: tuple[BlogPost, ...]

    @property
    def canonical_path(self) -> str:
        return self.route.canonical_path

    @property
    def canonical_url(self) -> str:
        return self.route.canonical_url
