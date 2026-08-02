"""Immutable Blog tag taxonomy models for the Site Compiler.

These are build-time, in-memory values produced by the tag taxonomy
builder.  They contain only plain Python types so no PyGithub object,
label interpretation, YAML parsing, or auxiliary slug map crosses into
templates or rendering.

The models are sufficient for the Blog Tags taxonomy (Ticket 07):
``TagSummary`` carries a single tag with its count and pre-computed
archive route for the tags index; ``TagArchiveEntry`` carries a single
post summary with pre-computed detail and tag paths for a tag archive;
``TagsIndex`` and ``TagArchive`` bundle fully-resolved pages so
templates never concatenate URLs; ``TagTaxonomyResult`` bundles the
index, archives, and accumulated diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..build_result import Diagnostic
from .blog_post import BlogTag


@dataclass(frozen=True)
class TagsIndexRoute:
    """Route for the Tags index page.

    The RouteRegistry-backed builder sets the values to ``/tags/`` and
    ``tags/index.html``.

    Attributes:
        canonical_path: Canonical URL path (e.g. ``/tags/``).
        output_path: Relative filesystem path (e.g. ``tags/index.html``).
    """

    canonical_path: str
    output_path: str


@dataclass(frozen=True)
class TagArchiveRoute:
    """Route for a single tag archive page.

    The RouteRegistry-backed builder sets the values to ``/tags/{key}/``
    and ``tags/{key}/index.html``.

    Attributes:
        canonical_path: Canonical URL path (e.g. ``/tags/python/``).
        output_path: Relative filesystem path
            (e.g. ``tags/python/index.html``).
    """

    canonical_path: str
    output_path: str


@dataclass(frozen=True)
class TagSummary:
    """A single tag summary in the tags index list.

    All URL paths are pre-computed by the producer so the template never
    concatenates path segments.

    Attributes:
        name: Display name for rendering (deterministic).
        count: Number of published Blog posts carrying this tag.
        route: Pre-computed route to this tag's archive page.
    """

    name: str
    count: int
    route: TagArchiveRoute


@dataclass(frozen=True)
class TagArchiveEntry:
    """A single post summary in a tag archive page.

    All URL paths are pre-computed by the RouteRegistry-backed builder so
    the template never concatenates path segments.

    Attributes:
        title: Display title of the post.
        created_date: ``YYYY-MM-DD`` string for display.
        detail_path: Pre-computed canonical URL path to the detail page
            (e.g. ``/blog/my-slug/``).
        tags: Tuple of immutable ``BlogTag`` values (name + path).
    """

    title: str
    created_date: str
    detail_path: str
    tags: tuple[BlogTag, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TagsIndex:
    """Fully resolved Tags index page ready for rendering.

    Every URL the template needs is pre-computed here: the page's own
    canonical route and per-tag archive routes.  Templates consume only
    this model and shared context.

    Attributes:
        route: This page's own route (canonical + output path).
        canonical_url: Absolute canonical URL from origin + canonical_path.
        tags: Tuple of ``TagSummary`` values, deterministically ordered.
    """

    route: TagsIndexRoute
    canonical_url: str
    tags: tuple[TagSummary, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TagArchive:
    """Fully resolved per-tag archive page ready for rendering.

    Every URL the template needs is pre-computed here: the page's own
    canonical route, the tags-index route for navigation, and per-entry
    detail and tag paths.  Templates consume only this model and shared
    context.

    Attributes:
        route: This page's own route (canonical + output path).
        canonical_url: Absolute canonical URL from origin + canonical_path.
        tag_name: Display name of the tag.
        index_route: Route of the Tags index page (for navigation back).
        entries: Tuple of ``TagArchiveEntry`` values, sorted by accepted
            Blog publication order.
    """

    route: TagArchiveRoute
    canonical_url: str
    tag_name: str
    index_route: TagsIndexRoute
    entries: tuple[TagArchiveEntry, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TagTaxonomyResult:
    """Result of building the Blog tag taxonomy from validated BlogPost values.

    Attributes:
        index: The Tags index page (always present, even when empty).
        archives: Tuple of per-tag archive pages.  Empty when no posts
            carry tags.
        diagnostics: Tuple of accumulated diagnostics.  Errors block
            rendering; warnings do not.
    """

    index: TagsIndex
    archives: tuple[TagArchive, ...] = field(default_factory=tuple)
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)

    @property
    def has_errors(self) -> bool:
        """True when any diagnostic is an error."""
        return any(d.severity == "error" for d in self.diagnostics)
