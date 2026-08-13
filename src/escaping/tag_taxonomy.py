from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from .build_result import Diagnostic
from .models.blog_post import BlogPost
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


@dataclass(frozen=True)
class _AggregatedTag:
    key: str
    display_name: str
    posts: tuple[BlogPost, ...]


def build_tag_taxonomy(
    posts: Sequence[BlogPost], routes: RouteRegistry
) -> TagTaxonomyResult:
    """Build Blog tags; SiteBuilder is the only production caller."""
    aggregated = _aggregate(posts)
    index_route = routes.tags()
    try:
        summaries = tuple(
            TagSummary(
                name=tag.display_name,
                count=len(tag.posts),
                route=routes.tag(tag.key),
            )
            for tag in aggregated
        )
        index = TagsIndex(route=index_route, tags=summaries)
        archives = tuple(_build_archive(tag, index_route, routes) for tag in aggregated)
    except (RouteCollisionError, ValueError) as exc:
        return TagTaxonomyResult(
            index=TagsIndex(route=index_route),
            diagnostics=(
                Diagnostic("error", "TAG_ROUTE_COLLISION", str(exc), field="route"),
            ),
        )
    return TagTaxonomyResult(index=index, archives=archives)


def _aggregate(posts: Sequence[BlogPost]) -> tuple[_AggregatedTag, ...]:
    tag_posts: dict[str, list[BlogPost]] = {}
    for post in posts:
        seen_keys: set[str] = set()
        for blog_tag in post.tags:
            key = _normalize_key(blog_tag.name)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            tag_posts.setdefault(key, []).append(post)
    return tuple(
        _AggregatedTag(key, key, tuple(tag_posts[key])) for key in sorted(tag_posts)
    )


def _build_archive(
    tag: _AggregatedTag, index_route: Route, routes: RouteRegistry
) -> TagArchive:
    posts = sorted(
        tag.posts,
        key=lambda post: (post.published_at, post.issue_number),
        reverse=True,
    )
    return TagArchive(
        route=routes.tag(tag.key),
        tag_name=tag.display_name,
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
