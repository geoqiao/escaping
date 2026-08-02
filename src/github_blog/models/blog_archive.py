"""Immutable Blog archive page models for the Site Compiler.

These are build-time, in-memory values produced by the archive builder.
They contain only plain Python types so no PyGithub object, label
interpretation, YAML parsing, or auxiliary slug map crosses into
templates or rendering.

The models are sufficient for the Blog archive (Ticket 05):
``ArchiveEntry`` carries a single post summary with pre-computed detail
and tag paths; ``ArchivePageRoute`` maps a canonical path to its output
filesystem path; ``ArchivePage`` bundles a paginated slice with
pre-computed prev/next routes so templates never concatenate URLs.
"""

from __future__ import annotations

from dataclasses import dataclass

from .blog_post import BlogTag


@dataclass(frozen=True)
class ArchiveEntry:
    """A single post summary in an archive page.

    All URL paths are pre-computed by the RouteRegistry-backed builder so the
    template never concatenates path segments.

    Attributes:
        title: Display title of the post.
        created_date: ``YYYY-MM-DD`` string for display.
        detail_path: Pre-computed canonical URL path to the detail page,
            e.g. ``/blog/my-slug/``.
        tags: Tuple of immutable ``BlogTag`` values (name + path).
    """

    title: str
    created_date: str
    detail_path: str
    tags: tuple[BlogTag, ...]


@dataclass(frozen=True)
class ArchivePageRoute:
    """A single archive page route mapping canonical URL to output path.

    Attributes:
        canonical_path: Canonical URL path with trailing slash for
            directory-index routes (``/blog/``, ``/blog/page/2/``).
        output_path: Relative filesystem path for the page's directory
            ``index.html`` (``blog/index.html``, ``blog/page/2/index.html``).
    """

    canonical_path: str
    output_path: str


@dataclass(frozen=True)
class ArchivePage:
    """A single paginated archive page, fully resolved for rendering.

    Every URL the template needs is pre-computed here: the page's own
    canonical route, adjacent prev/next routes, and per-entry detail
    and tag paths.  Templates consume only this model and shared context.

    Attributes:
        page_number: 1-indexed page number.
        total_pages: Total number of pages (>= 1).
        route: This page's own route (canonical + output path).
        canonical_url: Absolute canonical URL, pre-computed from the
            configured site origin and ``route.canonical_path``.
        prev_route: Route of the previous page, or ``None`` on page 1.
        next_route: Route of the next page, or ``None`` on the last page.
        entries: Tuple of ``ArchiveEntry`` values on this page.
    """

    page_number: int
    total_pages: int
    route: ArchivePageRoute
    canonical_url: str
    prev_route: ArchivePageRoute | None
    next_route: ArchivePageRoute | None
    entries: tuple[ArchiveEntry, ...]
