"""Internal Blog-only Atom model builder and XML renderer.

The SiteBuilder supplies immutable Site metadata and ``build_start_time``;
entries sort by accepted publication order
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

The strict SiteModel builder calls this component during every build; the
renderer receives only the resulting Atom model.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol

from .build_result import Diagnostic
from .models.atom_feed import (
    AtomEntry,
    AtomFeed,
    AtomFeedResult,
)
from .models.blog_post import BlogPost, blog_post_sort_key
from .routes import RouteRegistry

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Atom XML namespace (RFC 4287).
_ATOM_NS: str = "http://www.w3.org/2005/Atom"

# Register the default namespace so ElementTree serialises elements
# without a namespace prefix (standard Atom convention).
ET.register_namespace("", _ATOM_NS)


class _AtomMetadata(Protocol):
    title: str
    description: str
    author: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    utc_dt = dt.astimezone(UTC)
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
# Feed builder
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
        metadata: _AtomMetadata,
        *,
        build_start_time: datetime,
        route_registry: RouteRegistry,
    ) -> None:
        self._metadata = metadata
        self._build_start_time = build_start_time
        self._routes = route_registry
        self._atom_route = self._routes.atom()

    def _post_url(self, post: BlogPost) -> str:
        expected = f"{self._routes.origin}{post.route.canonical_path}"
        if post.route.canonical_url != expected:
            raise ValueError(
                f"Blog post Route uses a different site origin: {post.route.canonical_url!r}"
            )
        return post.route.canonical_url

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
            ("title", self._metadata.title),
            ("subtitle", self._metadata.description),
            ("author_name", self._metadata.author),
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
            absolute_url = self._post_url(post)
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
            key=blog_post_sort_key,
            reverse=True,
        )

        # Feed-level updated: max entry updated_at, or build_start_time.
        if sorted_posts:
            feed_updated = max(post.updated_at for post in sorted_posts)
        else:
            feed_updated = self._build_start_time

        entries = tuple(self._build_entry(post) for post in sorted_posts)

        feed = AtomFeed(
            route=self._atom_route,
            updated=feed_updated,
            entries=entries,
        )

        return AtomFeedResult(
            feed=feed,
            diagnostics=tuple(diagnostics),
        )

    def _build_entry(self, post: BlogPost) -> AtomEntry:
        """Build a single feed entry from a validated BlogPost."""
        absolute_url = self._post_url(post)
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


def _validate_feed_xml_chars(
    feed: AtomFeed, metadata: _AtomMetadata, home_url: str
) -> None:
    """Raise :class:`AtomXmlError` if any feed field has illegal XML 1.0 chars.

    Defense-in-depth: the builder excludes invalid entries and accumulates
    diagnostics, but this function ensures the renderer never produces a
    string that ``ET.fromstring`` cannot parse.  No content is silently
    deleted or replaced.
    """
    problems: list[str] = []

    for field_name, value in (
        ("title", metadata.title),
        ("subtitle", metadata.description),
        ("author_name", metadata.author),
        ("feed_id", home_url),
        ("self_url", feed.route.canonical_url),
        ("alternate_url", home_url),
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


def render_atom_xml(feed: AtomFeed, metadata: _AtomMetadata, home_url: str) -> str:
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
    _validate_feed_xml_chars(feed, metadata, home_url)

    feed_elem = ET.Element(f"{{{_ATOM_NS}}}feed")

    # --- Feed-level elements -----------------------------------------------
    id_elem = ET.SubElement(feed_elem, f"{{{_ATOM_NS}}}id")
    id_elem.text = home_url

    title_elem = ET.SubElement(feed_elem, f"{{{_ATOM_NS}}}title")
    title_elem.text = metadata.title

    # Self link (application/atom+xml)
    self_link = ET.SubElement(feed_elem, f"{{{_ATOM_NS}}}link")
    self_link.set("rel", "self")
    self_link.set("type", "application/atom+xml")
    self_link.set("href", feed.route.canonical_url)

    # Alternate link (text/html)
    alt_link = ET.SubElement(feed_elem, f"{{{_ATOM_NS}}}link")
    alt_link.set("rel", "alternate")
    alt_link.set("type", "text/html")
    alt_link.set("href", home_url)

    # Author
    author_elem = ET.SubElement(feed_elem, f"{{{_ATOM_NS}}}author")
    name_elem = ET.SubElement(author_elem, f"{{{_ATOM_NS}}}name")
    name_elem.text = metadata.author

    # Subtitle (site description)
    if metadata.description:
        subtitle_elem = ET.SubElement(feed_elem, f"{{{_ATOM_NS}}}subtitle")
        subtitle_elem.text = metadata.description

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
