"""Blog tag taxonomy builder - the taxonomy seam for Ticket 07.

Takes validated ``BlogPost`` values and explicitly injected ``Settings``,
aggregates tags from ``BlogPost.tags`` using NFC + casefold comparison
and deduplication, and produces immutable ``TagsIndex`` and ``TagArchive``
values with every route and link pre-computed before rendering.

Normalization rules:
- Tag comparison and deduplication use Unicode NFC + casefold.
- The display value is the NFC + casefold key (deterministic).
- Tags are sorted alphabetically by key for deterministic ordering.
- Same-post duplicate tags (after NFC + casefold) are counted once.

Route rules (strict):
- Tags index: ``/tags/`` -> ``tags/index.html``
- Tag archive: ``/tags/{key}/`` -> ``tags/{key}/index.html``
- Canonical absolute URLs are pre-computed from the configured origin.

Local route registration and collision detection are performed within
this builder.  The site-level dynamic RouteRegistry is Ticket 18's
responsibility.

The default production CLI does not call this strict builder. It remains
an expand/tracer seam while ``RenderService.render_tags_page`` and
``render_tag_page`` adapt the legacy pipeline to the same internal
taxonomy models.
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

#: Fixed strict Tags index route.
_TAGS_INDEX_ROUTE = TagsIndexRoute(
    canonical_path="/tags/",
    output_path="tags/index.html",
)

#: Fixed strict tag path prefix (canonical and output).
_TAGS_PATH = "tags"


def _normalize_key(name: str) -> str:
    """NFC normalize and casefold for case-insensitive comparison."""
    return unicodedata.normalize("NFC", name).casefold()


def _absolute_url(settings: Settings, canonical_path: str) -> str:
    """Join the configured HTTPS origin and a pre-computed absolute path."""
    return f"{str(settings.site.url).rstrip('/')}{canonical_path}"


def _strict_tag_route(key: str) -> TagArchiveRoute:
    """Return the fixed strict route for a tag archive."""
    return TagArchiveRoute(
        canonical_path=f"/{_TAGS_PATH}/{key}/",
        output_path=f"{_TAGS_PATH}/{key}/index.html",
    )


@dataclass(frozen=True)
class _AggregatedTag:
    """Internal aggregation state for a single unique tag."""

    key: str
    display_name: str
    posts: tuple[BlogPost, ...]


class TagTaxonomyBuilder:
    """Build strict tag taxonomy from validated ``BlogPost`` values.

    The builder is the taxonomy seam: validated posts and settings go
    in, a ``TagTaxonomyResult`` comes out.  No PyGithub object, label
    interpretation, or auxiliary slug map crosses this seam.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, posts: Sequence[BlogPost]) -> TagTaxonomyResult:
        """Build the tag taxonomy, always returning an index.

        Returns a ``TagTaxonomyResult``.  The index is always present
        (even when empty).  Archives are empty when no posts carry tags.
        """
        aggregated = self._aggregate(posts)
        diagnostics = self._check_collisions(aggregated)

        has_errors = any(d.severity == "error" for d in diagnostics)
        if has_errors:
            # Still produce an index so callers can render the empty state.
            index = TagsIndex(
                route=_TAGS_INDEX_ROUTE,
                canonical_url=_absolute_url(self._settings, "/tags/"),
                tags=(),
            )
            return TagTaxonomyResult(
                index=index,
                archives=(),
                diagnostics=tuple(diagnostics),
            )

        tags_summary = tuple(
            TagSummary(
                name=tag.display_name,
                count=len(tag.posts),
                route=_strict_tag_route(tag.key),
            )
            for tag in aggregated
        )

        index = TagsIndex(
            route=_TAGS_INDEX_ROUTE,
            canonical_url=_absolute_url(self._settings, "/tags/"),
            tags=tags_summary,
        )

        archives = tuple(self._build_archive(tag) for tag in aggregated)

        return TagTaxonomyResult(
            index=index,
            archives=archives,
            diagnostics=tuple(diagnostics),
        )

    def _aggregate(self, posts: Sequence[BlogPost]) -> tuple[_AggregatedTag, ...]:
        """Aggregate tags from BlogPost.tags with NFC + casefold dedup.

        Within each post, duplicate tags (by NFC + casefold key) are
        counted once.  Across posts, tags with the same key are merged.
        The display value is the NFC + casefold key (deterministic).
        Tags are sorted alphabetically by key.
        """
        # Map: key -> list of posts (each post appears at most once per key)
        tag_posts: dict[str, list[BlogPost]] = {}

        for post in posts:
            # Deduplicate tags within this post by key.
            seen_keys: set[str] = set()
            for blog_tag in post.tags:
                key = _normalize_key(blog_tag.name)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                if key not in tag_posts:
                    tag_posts[key] = []
                tag_posts[key].append(post)

        # Build aggregated tags sorted by key for deterministic ordering.
        return tuple(
            _AggregatedTag(
                key=key,
                display_name=key,
                posts=tuple(tag_posts[key]),
            )
            for key in sorted(tag_posts)
        )

    def _build_archive(self, tag: _AggregatedTag) -> TagArchive:
        """Build a single tag archive with entries sorted by publication order."""
        sorted_posts = sorted(
            tag.posts,
            key=lambda post: (post.published_at, post.issue_number),
            reverse=True,
        )
        return TagArchive(
            route=_strict_tag_route(tag.key),
            canonical_url=_absolute_url(self._settings, f"/{_TAGS_PATH}/{tag.key}/"),
            tag_name=tag.display_name,
            index_route=_TAGS_INDEX_ROUTE,
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

    def _check_collisions(
        self, aggregated: tuple[_AggregatedTag, ...]
    ) -> list[Diagnostic]:
        """Register local routes and detect canonical-path collisions.

        This is a local safety check: the builder already deduplicates
        tags by key, so collisions should not occur under normal
        operation.  The check exists to catch unexpected bugs and to
        provide an explicit, testable guarantee.

        The site-level dynamic RouteRegistry that derives the reserved
        set from every registered site page is Ticket 18's responsibility.
        """
        diagnostics: list[Diagnostic] = []
        seen: dict[str, str] = {}  # casefolded canonical_path -> tag key

        # Register the tags index route.
        index_key = _normalize_key(_TAGS_INDEX_ROUTE.canonical_path)
        seen[index_key] = "(tags-index)"

        # Register each tag archive route.
        for tag in aggregated:
            route = _strict_tag_route(tag.key)
            route_key = _normalize_key(route.canonical_path)
            if route_key in seen:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TAG_ROUTE_COLLISION",
                        message=(
                            f"Tag route {route.canonical_path!r} for tag "
                            f"{tag.display_name!r} collides with "
                            f"{seen[route_key]!r}"
                        ),
                    )
                )
            else:
                seen[route_key] = tag.display_name

        return diagnostics


# ---------------------------------------------------------------------------
# Writer tracers (strict, not connected to default CLI)
# ---------------------------------------------------------------------------


def write_tag_index(
    index: TagsIndex,
    render_html: Callable[[TagsIndex], str],
    output_dir: Path,
) -> tuple[Path, ...]:
    """Write a strict Tags index page to its pre-computed output path.

    This tracer is deliberately not connected to the default CLI. It
    writes the rendered page beneath ``output_dir`` using only
    ``index.route.output_path``.
    """
    path = output_dir / index.route.output_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(index), encoding="utf-8")
    return (path,)


def write_tag_archives(
    archives: Sequence[TagArchive],
    render_html: Callable[[TagArchive], str],
    output_dir: Path,
) -> tuple[Path, ...]:
    """Write strict tag archive pages to their pre-computed output paths.

    This tracer is deliberately not connected to the default CLI. It
    writes each rendered page beneath ``output_dir`` using only
    ``archive.route.output_path``.
    """
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
