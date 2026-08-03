from __future__ import annotations

from collections.abc import Sequence

from .models.blog_archive import ArchiveEntry, ArchivePage
from .models.blog_post import BlogPost
from .routes import RouteRegistry


def _build_archives(
    posts: Sequence[BlogPost], page_size: int, routes: RouteRegistry
) -> tuple[ArchivePage, ...]:
    """Build paginated Blog archives; SiteBuilder is the only caller."""
    sorted_posts = sorted(
        posts,
        key=lambda post: (post.published_at, post.issue_number),
        reverse=True,
    )
    page_slices = (
        [
            tuple(sorted_posts[start : start + page_size])
            for start in range(0, len(sorted_posts), page_size)
        ]
        if sorted_posts
        else [()]
    )
    total_pages = len(page_slices)
    pages: list[ArchivePage] = []
    for page_number, page_posts in enumerate(page_slices, start=1):
        pages.append(
            ArchivePage(
                page_number=page_number,
                total_pages=total_pages,
                route=routes.blog_archive(page_number),
                prev_route=(
                    routes.blog_archive(page_number - 1) if page_number > 1 else None
                ),
                next_route=(
                    routes.blog_archive(page_number + 1)
                    if page_number < total_pages
                    else None
                ),
                entries=tuple(
                    ArchiveEntry(
                        issue_number=post.issue_number,
                        title=post.title,
                        created_date=post.created_date,
                        detail_path=post.route.canonical_path,
                        tags=post.tags,
                    )
                    for post in page_posts
                ),
            )
        )
    return tuple(pages)
