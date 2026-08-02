"""Blog-only Atom feed builder, XML renderer, and writer (Ticket 08).

Takes validated ``BlogPost`` values and explicitly injected ``Settings``
plus ``build_start_time``, sorts entries by accepted publication order
(``published_at`` desc, ``issue_number`` desc), and produces an immutable
``AtomFeed`` with every URL pre-computed before rendering.

The feed route is fixed: ``/atom.xml`` -> ``atom.xml``.  The absolute
self URL is pre-computed from the Settings canonical origin.  Entry
``id`` and ``link`` come directly from ``BlogPost.canonical_path``
joined with the origin -- the renderer never concatenates or derives
alternative route semantics.

Timestamp handling:
- ``published`` = ``BlogPost.published_at`` (GitHub Issue ``created_at``).
- ``updated`` = ``BlogPost.updated_at`` (GitHub Issue ``updated_at``).
- Feed-level ``updated`` = max entry ``updated_at``, or the explicitly
  injected ``build_start_time`` when the feed is empty.
- All datetimes must be timezone-aware.  Naive datetimes produce a
  clear error diagnostic and the offending post is excluded from
  entries.  The RFC 3339 / UTC representation uses a trailing ``Z``.

The default production CLI does not call this strict builder. It remains
an expand/tracer seam while ``RenderService.generate_rss`` retains the
legacy production semantics.  Cutover is Ticket 22.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from pathlib import Path

from .build_result import Diagnostic
from .config import Settings
from .models.atom_feed import (
    AtomEntry,
    AtomFeed,
    AtomFeedResult,
    AtomFeedRoute,
)
from .models.blog_post import BlogPost

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Atom XML namespace (RFC 4287).
_ATOM_NS: str = "http://www.w3.org/2005/Atom"

#: Fixed feed route: canonical ``/atom.xml`` -> output ``atom.xml``.
_ATOM_FEED_ROUTE: AtomFeedRoute = AtomFeedRoute(
    canonical_path="/atom.xml",
    output_path="atom.xml",
)

# Register the default namespace so ElementTree serialises elements
# without a namespace prefix (standard Atom convention).
ET.register_namespace("", _ATOM_NS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _absolute_url(settings: Settings, canonical_path: str) -> str:
    """Join the configured HTTPS origin and a pre-computed absolute path."""
    return f"{str(settings.site.url).rstrip('/')}{canonical_path}"


def _is_aware(dt: datetime) -> bool:
    """Return True if *dt* is timezone-aware per Python semantics.

    Uses ``utcoffset() is not None`` rather than just checking ``tzinfo``
    because a ``tzinfo`` object may be set yet report ``utcoffset() is
    None``.  Exceptions from exotic tzinfo implementations are safely
    treated as naive.
    """
    try:
        return dt.utcoffset() is not None
    except Exception:  # safely handle broken tzinfo
        return False


def _format_rfc3339(dt: datetime) -> str:
    """Format an aware datetime as RFC 3339 in UTC with a ``Z`` suffix.

    Raises:
        ValueError: if *dt* is naive (``utcoffset() is None``).
    """
    if not _is_aware(dt):
        raise ValueError(
            f"Cannot format naive datetime {dt!r} as RFC 3339; "
            "timezone-aware datetime required"
        )
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# XML 1.0 character validation
# ---------------------------------------------------------------------------


class AtomXmlError(ValueError):
    """Raised when Atom feed content contains illegal XML 1.0 characters.

    Subclasses :class:`ValueError` so callers catching ``ValueError``
    (e.g. the naive-datetime defense) also catch this.
    """


def _is_valid_xml_1_0_code_point(cp: int) -> bool:
    """Return True if *cp* is a valid XML 1.0 character code point.

    Per XML 1.0 (5th edition), the only allowed characters are::

        #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]

    TAB (U+0009), LF (U+000A), and CR (U+000D) are the only legal
    control characters.
    """
    return (
        cp == 0x9
        or cp == 0xA
        or cp == 0xD
        or 0x20 <= cp <= 0xD7FF
        or 0xE000 <= cp <= 0xFFFD
        or 0x10000 <= cp <= 0x10FFFF
    )


def _find_illegal_xml_char(value: str) -> int | None:
    """Return the index of the first illegal XML 1.0 character, or None.

    Returns ``None`` when *value* is empty or every character is a legal
    XML 1.0 code point.  No content is modified or removed.
    """
    for i, ch in enumerate(value):
        if not _is_valid_xml_1_0_code_point(ord(ch)):
            return i
    return None


# ---------------------------------------------------------------------------
# AtomFeedBuilder
# ---------------------------------------------------------------------------


class AtomFeedBuilder:
    """Build a strict Blog-only Atom feed from validated ``BlogPost`` values.

    The builder is the feed seam: validated posts, settings, and an
    explicit build start time go in, an ``AtomFeedResult`` comes out.
    No PyGithub object, label interpretation, or front matter crosses
    this seam.

    Timestamp validation: GitHub datetimes should be timezone-aware.
    Naive ``published_at`` or ``updated_at`` on any post produces a
    clear error diagnostic and the post is excluded from entries.
    Naive ``build_start_time`` produces an error diagnostic.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        build_start_time: datetime,
    ) -> None:
        self._settings = settings
        self._build_start_time = build_start_time

    def build(self, posts: Sequence[BlogPost]) -> AtomFeedResult:
        """Build the Atom feed, always returning a valid ``AtomFeed``.

        Returns an ``AtomFeedResult``.  The feed is always present (even
        when entries are empty or diagnostics exist).  Diagnostics with
        severity ``error`` indicate invalid timestamps and should
        prevent rendering.
        """
        diagnostics: list[Diagnostic] = []

        # Validate build_start_time timezone awareness.
        if not _is_aware(self._build_start_time):
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="ATOM_NAIVE_BUILD_START_TIME",
                    message=(
                        f"build_start_time {self._build_start_time!r} is "
                        "naive; timezone-aware datetime required"
                    ),
                    field="build_start_time",
                )
            )

        # Validate site-level XML 1.0 character validity.
        for field_name, value in (
            ("title", self._settings.site.title),
            ("subtitle", self._settings.site.description),
            ("author_name", self._settings.site.author),
        ):
            pos = _find_illegal_xml_char(value)
            if pos is not None:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="ATOM_XML_INVALID_CHAR",
                        message=(
                            f"site {field_name} contains an illegal "
                            f"XML 1.0 control character at position "
                            f"{pos} (U+{ord(value[pos]):04X})"
                        ),
                        field=field_name,
                    )
                )

        # Validate post timestamps and XML chars; collect valid posts.
        valid_posts: list[BlogPost] = []
        for post in posts:
            post_has_errors = False

            # Timestamp awareness: check published_at and updated_at
            # independently so both are reported when both are invalid.
            if not _is_aware(post.published_at):
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="ATOM_NAIVE_PUBLISHED_AT",
                        message=(
                            f"Issue #{post.issue_number}: published_at "
                            f"{post.published_at!r} is naive; "
                            "timezone-aware datetime required"
                        ),
                        issue_number=post.issue_number,
                        field="published_at",
                    )
                )
                post_has_errors = True

            if not _is_aware(post.updated_at):
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="ATOM_NAIVE_UPDATED_AT",
                        message=(
                            f"Issue #{post.issue_number}: updated_at "
                            f"{post.updated_at!r} is naive; "
                            "timezone-aware datetime required"
                        ),
                        issue_number=post.issue_number,
                        field="updated_at",
                    )
                )
                post_has_errors = True

            # XML 1.0 character validation for entry fields.
            absolute_url = _absolute_url(self._settings, post.canonical_path)
            for field_name, value in (
                ("title", post.title),
                ("summary", post.description),
                ("id", absolute_url),
                ("content_html", post.body_html),
            ):
                pos = _find_illegal_xml_char(value)
                if pos is not None:
                    diagnostics.append(
                        Diagnostic(
                            severity="error",
                            code="ATOM_XML_INVALID_CHAR",
                            message=(
                                f"Issue #{post.issue_number}: "
                                f"{field_name} contains an illegal "
                                f"XML 1.0 control character at position "
                                f"{pos} (U+{ord(value[pos]):04X})"
                            ),
                            issue_number=post.issue_number,
                            field=field_name,
                        )
                    )
                    post_has_errors = True

            if not post_has_errors:
                valid_posts.append(post)

        # Sort by accepted publication order: published_at desc,
        # issue_number desc.
        sorted_posts = sorted(
            valid_posts,
            key=lambda post: (post.published_at, post.issue_number),
            reverse=True,
        )

        # Feed-level updated: max entry updated_at, or build_start_time.
        if sorted_posts:
            feed_updated = max(post.updated_at for post in sorted_posts)
        else:
            feed_updated = self._build_start_time

        entries = tuple(self._build_entry(post) for post in sorted_posts)

        feed = AtomFeed(
            route=_ATOM_FEED_ROUTE,
            self_url=_absolute_url(self._settings, _ATOM_FEED_ROUTE.canonical_path),
            alternate_url=_absolute_url(self._settings, "/"),
            feed_id=_absolute_url(self._settings, "/"),
            title=self._settings.site.title,
            subtitle=self._settings.site.description,
            author_name=self._settings.site.author,
            updated=feed_updated,
            entries=entries,
        )

        return AtomFeedResult(
            feed=feed,
            diagnostics=tuple(diagnostics),
        )

    def _build_entry(self, post: BlogPost) -> AtomEntry:
        """Build a single feed entry from a validated BlogPost."""
        absolute_url = _absolute_url(self._settings, post.canonical_path)
        return AtomEntry(
            id=absolute_url,
            title=post.title,
            link=absolute_url,
            summary=post.description,
            published=post.published_at,
            updated=post.updated_at,
            content_html=post.body_html,
        )


# ---------------------------------------------------------------------------
# XML renderer
# ---------------------------------------------------------------------------


def _validate_feed_xml_chars(feed: AtomFeed) -> None:
    """Raise :class:`AtomXmlError` if any feed field has illegal XML 1.0 chars.

    Defense-in-depth: the builder excludes invalid entries and accumulates
    diagnostics, but this function ensures the renderer never produces a
    string that ``ET.fromstring`` cannot parse.  No content is silently
    deleted or replaced.
    """
    problems: list[str] = []

    for field_name, value in (
        ("title", feed.title),
        ("subtitle", feed.subtitle),
        ("author_name", feed.author_name),
        ("feed_id", feed.feed_id),
        ("self_url", feed.self_url),
        ("alternate_url", feed.alternate_url),
    ):
        pos = _find_illegal_xml_char(value)
        if pos is not None:
            problems.append(
                f"feed {field_name}: illegal XML 1.0 character "
                f"U+{ord(value[pos]):04X} at position {pos}"
            )

    for entry in feed.entries:
        entry_fields: list[tuple[str, str]] = [
            ("id", entry.id),
            ("title", entry.title),
            ("link", entry.link),
            ("summary", entry.summary),
        ]
        if entry.content_html is not None:
            entry_fields.append(("content_html", entry.content_html))
        for field_name, value in entry_fields:
            pos = _find_illegal_xml_char(value)
            if pos is not None:
                problems.append(
                    f"entry {field_name}: illegal XML 1.0 character "
                    f"U+{ord(value[pos]):04X} at position {pos}"
                )

    if problems:
        raise AtomXmlError(
            "illegal XML 1.0 character(s) detected: " + "; ".join(problems)
        )


def render_atom_xml(feed: AtomFeed) -> str:
    """Render an ``AtomFeed`` as a valid Atom XML string (UTF-8).

    Produces a standard Atom 1.0 document with the correct XML namespace,
    ``<link rel="self" type="application/atom+xml">``, alternate links,
    and per-entry ``<id>``, ``<title>``, ``<link>``, ``<summary>``,
    ``<published>``, ``<updated>``, and optional ``<content type="html">``.

    All text content is XML-escaped by ElementTree.  Datetimes are
    formatted as RFC 3339 / UTC with a trailing ``Z``.

    Raises:
        AtomXmlError: if any field contains an illegal XML 1.0 character
            (defense-in-depth; the builder should have excluded such
            entries already).
        ValueError: if any datetime is naive.
    """
    # Defense-in-depth: reject illegal XML 1.0 characters before
    # serialization so the renderer never returns unparseable XML.
    _validate_feed_xml_chars(feed)

    feed_elem = ET.Element(f"{{{_ATOM_NS}}}feed")

    # --- Feed-level elements -----------------------------------------------
    id_elem = ET.SubElement(feed_elem, f"{{{_ATOM_NS}}}id")
    id_elem.text = feed.feed_id

    title_elem = ET.SubElement(feed_elem, f"{{{_ATOM_NS}}}title")
    title_elem.text = feed.title

    # Self link (application/atom+xml)
    self_link = ET.SubElement(feed_elem, f"{{{_ATOM_NS}}}link")
    self_link.set("rel", "self")
    self_link.set("type", "application/atom+xml")
    self_link.set("href", feed.self_url)

    # Alternate link (text/html)
    alt_link = ET.SubElement(feed_elem, f"{{{_ATOM_NS}}}link")
    alt_link.set("rel", "alternate")
    alt_link.set("type", "text/html")
    alt_link.set("href", feed.alternate_url)

    # Author
    author_elem = ET.SubElement(feed_elem, f"{{{_ATOM_NS}}}author")
    name_elem = ET.SubElement(author_elem, f"{{{_ATOM_NS}}}name")
    name_elem.text = feed.author_name

    # Subtitle (site description)
    if feed.subtitle:
        subtitle_elem = ET.SubElement(feed_elem, f"{{{_ATOM_NS}}}subtitle")
        subtitle_elem.text = feed.subtitle

    # Feed-level updated
    updated_elem = ET.SubElement(feed_elem, f"{{{_ATOM_NS}}}updated")
    updated_elem.text = _format_rfc3339(feed.updated)

    # --- Entries -----------------------------------------------------------
    for entry in feed.entries:
        entry_elem = ET.SubElement(feed_elem, f"{{{_ATOM_NS}}}entry")

        entry_id = ET.SubElement(entry_elem, f"{{{_ATOM_NS}}}id")
        entry_id.text = entry.id

        entry_title = ET.SubElement(entry_elem, f"{{{_ATOM_NS}}}title")
        entry_title.text = entry.title

        entry_link = ET.SubElement(entry_elem, f"{{{_ATOM_NS}}}link")
        entry_link.set("rel", "alternate")
        entry_link.set("type", "text/html")
        entry_link.set("href", entry.link)

        entry_summary = ET.SubElement(entry_elem, f"{{{_ATOM_NS}}}summary")
        entry_summary.text = entry.summary

        entry_published = ET.SubElement(entry_elem, f"{{{_ATOM_NS}}}published")
        entry_published.text = _format_rfc3339(entry.published)

        entry_updated = ET.SubElement(entry_elem, f"{{{_ATOM_NS}}}updated")
        entry_updated.text = _format_rfc3339(entry.updated)

        if entry.content_html is not None:
            entry_content = ET.SubElement(entry_elem, f"{{{_ATOM_NS}}}content")
            entry_content.set("type", "html")
            entry_content.text = entry.content_html

    xml_bytes = ET.tostring(
        feed_elem,
        encoding="utf-8",
        xml_declaration=True,
    )
    return xml_bytes.decode("utf-8")


# ---------------------------------------------------------------------------
# Writer tracer (strict, not connected to default CLI)
# ---------------------------------------------------------------------------


def write_atom_feed(
    feed: AtomFeed,
    render_xml: Callable[[AtomFeed], str],
    output_dir: Path,
) -> Path:
    """Write the Atom feed XML to its pre-computed output path.

    This tracer is deliberately not connected to the default CLI. It
    writes the feed beneath ``output_dir`` using only
    ``feed.route.output_path``.
    """
    path = output_dir / feed.route.output_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_xml(feed), encoding="utf-8")
    return path


__all__ = [
    "AtomFeedBuilder",
    "AtomXmlError",
    "render_atom_xml",
    "write_atom_feed",
]
