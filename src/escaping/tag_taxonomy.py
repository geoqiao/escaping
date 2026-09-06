from __future__ import annotations

import unicodedata
from collections.abc import Sequence

from .build_result import Diagnostic
from .models.blog_post import BlogPost, blog_post_sort_key
from .models.tag_taxonomy import (
    TagArchive,
    TagArchiveEntry,
    TagsIndex,
    TagSummary,
    TagTaxonomyResult,
)
from .routes import Route, RouteCollisionError, RouteRegistry


def _normalize_key(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


def build_tag_taxonomy(
    posts: Sequence[BlogPost], routes: RouteRegistry
) -> TagTaxonomyResult:
    """Build Blog tags; SiteBuilder is the only production caller."""
    aggregated = _aggregate(posts)
    index_route = routes.tags()
    try:
        summaries = tuple(
            TagSummary(
                name=key,
                count=len(aggregated[key]),
                route=routes.tag(key),
            )
            for key in sorted(aggregated)
        )
        index = TagsIndex(route=index_route, tags=summaries)
        archives = tuple(
            _build_archive(tag, aggregated[tag.name], index_route) for tag in summaries
        )
    except (RouteCollisionError, ValueError) as exc:
        return TagTaxonomyResult(
            index=TagsIndex(route=index_route),
            diagnostics=(
                Diagnostic("error", "TAG_ROUTE_COLLISION", str(exc), field="route"),
            ),
        )
    return TagTaxonomyResult(index=index, archives=archives)


def _aggregate(posts: Sequence[BlogPost]) -> dict[str, list[BlogPost]]:
    tag_posts: dict[str, list[BlogPost]] = {}
    for post in posts:
        seen_keys: set[str] = set()
        for blog_tag in post.tags:
            key = _normalize_key(blog_tag.name)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            tag_posts.setdefault(key, []).append(post)
    return tag_posts


def _build_archive(
    tag: TagSummary, posts: Sequence[BlogPost], index_route: Route
) -> TagArchive:
    posts = sorted(
        posts,
        key=blog_post_sort_key,
        reverse=True,
    )
    return TagArchive(
        route=tag.route,
        tag_name=tag.name,
        index_route=index_route,
        entries=tuple(
            TagArchiveEntry(
                issue_number=post.issue_number,
                title=post.title,
                created_date=post.created_date,
                detail_path=post.route.canonical_path,
                tags=post.tags,
            )
            for post in posts
        ),
    )
