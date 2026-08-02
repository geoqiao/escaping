"""Build the Blog tag taxonomy from validated models.

Tags are normalized with NFC + casefold, deduplicated per post, and resolved
through the shared RouteRegistry before templates or artifact writers see the
models.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .build_result import Diagnostic
from .config import Settings
from .models.blog_post import BlogPost
from .models.tag_taxonomy import (
    TagArchive,
    TagArchiveEntry,
    TagArchiveRoute,
    TagsIndex,
    TagsIndexRoute,
    TagSummary,
    TagTaxonomyResult,
)
from .routes import Route, RouteCollisionError, RouteRegistry


def _normalize_key(name: str) -> str:
    """NFC normalize and casefold for case-insensitive comparison."""
    return unicodedata.normalize("NFC", name).casefold()


def _tags_index_route(route: Route) -> TagsIndexRoute:
    return TagsIndexRoute(route.canonical_path, route.output_path)


def _tag_archive_route(route: Route) -> TagArchiveRoute:
    return TagArchiveRoute(route.canonical_path, route.output_path)


@dataclass(frozen=True)
class _AggregatedTag:
    key: str
    display_name: str
    posts: tuple[BlogPost, ...]


class TagTaxonomyBuilder:
    """Build the Blog tag taxonomy using one injected RouteRegistry."""

    def __init__(
        self, settings: Settings, route_registry: RouteRegistry | None = None
    ) -> None:
        self._routes = route_registry or RouteRegistry(str(settings.site.url))

    def build(self, posts: Sequence[BlogPost]) -> TagTaxonomyResult:
        """Build the taxonomy, always returning a valid index model."""
        aggregated = self._aggregate(posts)
        index_route = _tags_index_route(self._routes.tags())
        try:
            summaries = tuple(
                TagSummary(
                    name=tag.display_name,
                    count=len(tag.posts),
                    route=_tag_archive_route(self._routes.tag(tag.key)),
                )
                for tag in aggregated
            )
            index = TagsIndex(
                route=index_route,
                canonical_url=self._routes.url(self._routes.tags()),
                tags=summaries,
            )
            archives = tuple(
                self._build_archive(tag, index_route) for tag in aggregated
            )
        except (RouteCollisionError, ValueError) as exc:
            diagnostic = Diagnostic(
                "error", "TAG_ROUTE_COLLISION", str(exc), field="route"
            )
            index = TagsIndex(
                route=index_route,
                canonical_url=self._routes.url(self._routes.tags()),
                tags=(),
            )
            return TagTaxonomyResult(
                index=index, archives=(), diagnostics=(diagnostic,)
            )

        return TagTaxonomyResult(index=index, archives=archives)

    def _aggregate(self, posts: Sequence[BlogPost]) -> tuple[_AggregatedTag, ...]:
        """Aggregate tags with NFC + casefold and same-post deduplication."""
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
        self, tag: _AggregatedTag, index_route: TagsIndexRoute
    ) -> TagArchive:
        sorted_posts = sorted(
            tag.posts,
            key=lambda post: (post.published_at, post.issue_number),
            reverse=True,
        )
        route = self._routes.tag(tag.key)
        return TagArchive(
            route=_tag_archive_route(route),
            canonical_url=self._routes.url(route),
            tag_name=tag.display_name,
            index_route=index_route,
            entries=tuple(
                TagArchiveEntry(
                    title=post.title,
                    created_date=post.created_date,
                    detail_path=post.canonical_path,
                    tags=post.tags,
                )
                for post in sorted_posts
            ),
        )


def write_tag_index(
    index: TagsIndex,
    render_html: Callable[[TagsIndex], str],
    output_dir: Path,
) -> tuple[Path, ...]:
    """Write a Tags index model to its pre-computed output path."""
    path = output_dir / index.route.output_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(index), encoding="utf-8")
    return (path,)


def write_tag_archives(
    archives: Sequence[TagArchive],
    render_html: Callable[[TagArchive], str],
    output_dir: Path,
) -> tuple[Path, ...]:
    """Write tag archive models to their pre-computed output paths."""
    written: list[Path] = []
    for archive in archives:
        path = output_dir / archive.route.output_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_html(archive), encoding="utf-8")
        written.append(path)
    return tuple(written)


__all__ = [
    "TagTaxonomyBuilder",
    "TagTaxonomyResult",
    "write_tag_archives",
    "write_tag_index",
]
