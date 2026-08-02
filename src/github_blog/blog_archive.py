"""Blog archive builder - the pagination seam for Ticket 05.

Takes validated ``BlogPost`` values and explicitly injected ``Settings``,
sorts them deterministically, and produces immutable ``ArchivePage`` values
with every route and link pre-computed before rendering.

The strict SiteModel builder calls this component during every build; the
renderer receives only the resulting archive models.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from .config import Settings
from .models.blog_archive import ArchiveEntry, ArchivePage, ArchivePageRoute
from .models.blog_post import BlogPost

_STRICT_BLOG_PATH = "blog"
_STRICT_PAGE_PATH = "page"


class BlogArchiveBuilder:
    """Build strict paginated archive pages from validated ``BlogPost`` values."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, posts: Sequence[BlogPost]) -> tuple[ArchivePage, ...]:
        """Build deterministic archive pages, always returning at least one.

        Posts sort by GitHub publication timestamp (``published_at``)
        descending, with Issue number descending as the tie-breaker. Pagination
        uses the validated positive ``settings.paths.page_size`` value.
        """
        sorted_posts = sorted(
            posts,
            key=lambda post: (post.published_at, post.issue_number),
            reverse=True,
        )
        page_size = self._settings.paths.page_size
        page_slices = (
            [
                tuple(sorted_posts[start : start + page_size])
                for start in range(0, len(sorted_posts), page_size)
            ]
            if sorted_posts
            else [()]
        )
        total_pages = len(page_slices)

        return tuple(
            self._build_page(page_number, total_pages, page_posts)
            for page_number, page_posts in enumerate(page_slices, start=1)
        )

    def _build_page(
        self,
        page_number: int,
        total_pages: int,
        posts: tuple[BlogPost, ...],
    ) -> ArchivePage:
        route = _strict_page_route(page_number)
        return ArchivePage(
            page_number=page_number,
            total_pages=total_pages,
            route=route,
            canonical_url=_absolute_url(self._settings, route.canonical_path),
            prev_route=(
                _strict_page_route(page_number - 1) if page_number > 1 else None
            ),
            next_route=(
                _strict_page_route(page_number + 1)
                if page_number < total_pages
                else None
            ),
            entries=tuple(
                ArchiveEntry(
                    issue_number=post.issue_number,
                    title=post.title,
                    created_date=post.created_date,
                    detail_path=post.canonical_path,
                    tags=post.tags,
                )
                for post in posts
            ),
        )


def _strict_page_route(page_number: int) -> ArchivePageRoute:
    """Return the fixed strict route for a 1-indexed archive page."""
    if page_number == 1:
        return ArchivePageRoute(
            canonical_path=f"/{_STRICT_BLOG_PATH}/",
            output_path=f"{_STRICT_BLOG_PATH}/index.html",
        )
    return ArchivePageRoute(
        canonical_path=f"/{_STRICT_BLOG_PATH}/{_STRICT_PAGE_PATH}/{page_number}/",
        output_path=(
            f"{_STRICT_BLOG_PATH}/{_STRICT_PAGE_PATH}/{page_number}/index.html"
        ),
    )


def _absolute_url(settings: Settings, canonical_path: str) -> str:
    """Join the configured HTTPS origin and a pre-computed absolute path."""
    return f"{str(settings.site.url).rstrip('/')}{canonical_path}"


def write_archive_pages(
    pages: Sequence[ArchivePage],
    render_html: Callable[[ArchivePage], str],
    output_dir: Path,
) -> tuple[Path, ...]:
    """Write strict archive pages to their pre-computed output paths.

    This focused writer remains useful for component tests. It writes each
    rendered page beneath ``output_dir`` using the model route.
    """
    written: list[Path] = []
    for page in pages:
        path = output_dir / page.route.output_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_html(page), encoding="utf-8")
        written.append(path)
    return tuple(written)
