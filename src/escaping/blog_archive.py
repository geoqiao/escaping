from __future__ import annotations

from collections.abc import Sequence

from .models.blog_archive import ArchivePage
from .models.blog_post import BlogPost, blog_post_sort_key
from .routes import RouteRegistry


def build_archives(
    posts: Sequence[BlogPost], page_size: int, routes: RouteRegistry
) -> tuple[ArchivePage, ...]:
    """Paginate the Blog archive, newest first; an empty Blog has one page."""
    ordered = sorted(posts, key=blog_post_sort_key, reverse=True)
    slices = [
        tuple(ordered[start : start + page_size])
        for start in range(0, len(ordered), page_size)
    ] or [()]
    total = len(slices)
    return tuple(
        ArchivePage(
            page_number=number,
            total_pages=total,
            route=routes.blog_archive(number),
            prev_route=routes.blog_archive(number - 1) if number > 1 else None,
            next_route=routes.blog_archive(number + 1) if number < total else None,
            posts=page_posts,
        )
        for number, page_posts in enumerate(slices, start=1)
    )
