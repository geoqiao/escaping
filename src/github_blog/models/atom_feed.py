"""Immutable Atom feed models for the Site Compiler.

These are build-time, in-memory values produced by the Atom feed builder.
They contain only plain Python types so no PyGithub object, label
interpretation, YAML parsing, or auxiliary slug map crosses into the XML
renderer or writer.

The models are sufficient for the Blog-only Atom feed (Ticket 08):
``AtomFeedRoute`` maps the fixed ``/atom.xml`` canonical path to its
``atom.xml`` output file; ``AtomEntry`` carries a single fully-resolved
feed entry whose id/link come directly from ``BlogPost.canonical_path``;
``AtomFeed`` bundles the feed with pre-computed self/alternate URLs and
entries sorted by accepted publication order; ``AtomFeedResult`` bundles
the feed with accumulated diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..build_result import Diagnostic


@dataclass(frozen=True)
class AtomFeedRoute:
    """Fixed route for the Atom feed.

    The route is not configurable: canonical ``/atom.xml`` maps to the
    output file ``atom.xml``.

    Attributes:
        canonical_path: Canonical URL path (``/atom.xml``).
        output_path: Relative filesystem path (``atom.xml``).
    """

    canonical_path: str
    output_path: str


@dataclass(frozen=True)
class AtomEntry:
    """A single Atom feed entry, fully resolved from a validated BlogPost.

    Every URL the renderer needs is pre-computed by the builder so the
    XML renderer never concatenates path segments or derives routes.

    Attributes:
        id: Absolute canonical URL for the entry (from
            ``BlogPost.canonical_path`` joined with the site origin).
            Serves as both the Atom ``<id>`` and the ``<link>`` href.
        title: Entry title from ``BlogPost.title``.
        link: Absolute URL to the HTML detail page (same as ``id``).
        summary: Plain-text summary from validated
            ``BlogPost.description`` (never contains front matter).
        published: Publication timestamp from ``BlogPost.published_at``
            (GitHub Issue ``created_at``).
        updated: Update timestamp from ``BlogPost.updated_at``
            (GitHub Issue ``updated_at``).
        content_html: Optional sanitized HTML body from
            ``BlogPost.body_html``.  When present, rendered as
            ``<content type="html">``.
    """

    id: str
    title: str
    link: str
    summary: str
    published: datetime
    updated: datetime
    content_html: str | None


@dataclass(frozen=True)
class AtomFeed:
    """Fully resolved Atom feed ready for XML rendering.

    Every URL the renderer needs is pre-computed here: the feed's own
    route, absolute self URL, alternate (HTML) URL, feed ID, and
    per-entry id/link values.  The XML renderer consumes only this model.

    Attributes:
        route: Fixed feed route (canonical ``/atom.xml`` -> ``atom.xml``).
        self_url: Absolute self URL (origin + ``/atom.xml``).
        alternate_url: Absolute HTML site URL (origin + ``/``).
        feed_id: Absolute feed identifier URL (origin + ``/``).
        title: Feed title from ``Settings.site.title``.
        subtitle: Feed subtitle from ``Settings.site.description``.
        author_name: Author display name from ``Settings.site.author``.
        updated: Feed-level updated timestamp.  When entries exist, this
            is the maximum entry ``updated_at``.  When empty, this is the
            explicitly injected build start time.
        entries: Tuple of ``AtomEntry`` values sorted by accepted
            publication order (``published_at`` desc, ``issue_number``
            desc).
    """

    route: AtomFeedRoute
    self_url: str
    alternate_url: str
    feed_id: str
    title: str
    subtitle: str
    author_name: str
    updated: datetime
    entries: tuple[AtomEntry, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AtomFeedResult:
    """Result of building the Atom feed from validated BlogPost values.

    Attributes:
        feed: The fully resolved ``AtomFeed`` (always present, even when
            entries are empty or errors exist).
        diagnostics: Tuple of accumulated diagnostics.  Errors indicate
            invalid timestamps (e.g. naive datetimes) and should prevent
            rendering; warnings do not.
    """

    feed: AtomFeed
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)

    @property
    def has_errors(self) -> bool:
        """True when any diagnostic is an error."""
        return any(d.severity == "error" for d in self.diagnostics)
