"""Allowlist-based HTML sanitizer using only the Python standard library.

Runs **after** Markdown rendering and after front-matter removal. Preserves
normal paragraphs, headings, lists, tables, images, links, blockquotes,
emphasis, and code while removing scripts, styles, iframes, objects, embeds,
forms, event-handler attributes, and dangerous URL schemes.

Implementation uses ``html.parser.HTMLParser`` (stdlib) to walk the HTML token
stream and rebuild only allowlisted elements with allowlisted attributes.

No new dependencies are introduced.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

#: Elements that are completely removed (tag, content, and children).
#: These are dangerous embeds, scripting, or interactive elements that
#: are **containers** - they have closing tags and their content must be
#: suppressed along with the tag.
_DANGEROUS_CONTAINER_TAGS: frozenset[str] = frozenset(
    {
        "script",
        "style",
        "iframe",
        "object",
        "form",
        "button",
        "textarea",
        "select",
        "option",
        "applet",
        "frameset",
        "noscript",
        "template",
        "slot",
    }
)

#: Dangerous **void** elements - tags that have no closing tag in HTML.
#: These are dropped themselves without entering suppress mode, because
#: there is no reliable end tag to match.  Entering suppress mode would
#: swallow all subsequent safe siblings and body text.  This covers GFM
#: task-list ``<input>`` as well as ``embed``, ``meta``, ``link``,
#: ``base``, and ``frame``.
_DANGEROUS_VOID_TAGS: frozenset[str] = frozenset(
    {
        "input",
        "embed",
        "meta",
        "link",
        "base",
        "frame",
    }
)

#: Union of all dangerous tags (containers + void).
_DANGEROUS_TAGS: frozenset[str] = _DANGEROUS_CONTAINER_TAGS | _DANGEROUS_VOID_TAGS

#: Elements allowed in the output. Everything not in this set (and not in
#: ``_DANGEROUS_TAGS``) is unwrapped: its children are kept but the tag itself
#: is dropped.
_ALLOWED_TAGS: frozenset[str] = frozenset(
    {
        # Block structure
        "p",
        "div",
        "br",
        "hr",
        # Headings
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        # Lists
        "ul",
        "ol",
        "li",
        "dl",
        "dt",
        "dd",
        # Tables
        "table",
        "thead",
        "tbody",
        "tfoot",
        "tr",
        "td",
        "th",
        "caption",
        "colgroup",
        "col",
        # Inline
        "a",
        "span",
        "em",
        "strong",
        "code",
        "pre",
        "img",
        "blockquote",
        "del",
        "ins",
        "sub",
        "sup",
        "mark",
        "small",
        "abbr",
        "cite",
        "q",
        "kbd",
        "samp",
        "var",
        "time",
        "s",
        "u",
        # Sectioning
        "section",
        "article",
        "header",
        "footer",
        "aside",
        "nav",
        "figure",
        "figcaption",
        "details",
        "summary",
        "hgroup",
        # Line break / word break
        "wbr",
    }
)

#: Attributes allowed on specific elements.  ``*`` means any element.
#: The value is a frozenset of attribute names.
_ALLOWED_ATTRS: dict[str, frozenset[str]] = {
    "*": frozenset(),
    "a": frozenset({"href", "title"}),
    "img": frozenset({"src", "alt", "title", "width", "height", "loading", "decoding"}),
    "td": frozenset({"colspan", "rowspan", "align"}),
    "th": frozenset({"colspan", "rowspan", "align", "scope"}),
    "col": frozenset({"span", "align"}),
    "colgroup": frozenset({"span"}),
    "time": frozenset({"datetime"}),
    "q": frozenset({"cite"}),
    "blockquote": frozenset({"cite"}),
    "del": frozenset({"cite", "datetime"}),
    "ins": frozenset({"cite", "datetime"}),
    "code": frozenset({"class"}),
    "pre": frozenset({"class"}),
    "span": frozenset({"class"}),
    "div": frozenset({"class"}),
    "section": frozenset({"class"}),
    "article": frozenset({"class"}),
    "header": frozenset({"class"}),
    "footer": frozenset({"class"}),
    "aside": frozenset({"class"}),
    "details": frozenset({"open"}),
}

#: URL schemes considered safe for ``href`` and ``src`` attributes.
#: Empty string (relative URLs) and fragment-only URLs are also safe.
_SAFE_SCHEMES: frozenset[str] = frozenset(
    {
        "http",
        "https",
        "mailto",
        "tel",
        "ftp",
        "ftps",
        "",
    }
)

#: Attributes whose values are URLs and must be scheme-checked.
_URL_ATTRS: frozenset[str] = frozenset({"href", "src", "cite"})

_ENUM_ATTR_VALUES: dict[str, frozenset[str]] = {
    "loading": frozenset({"eager", "lazy"}),
    "decoding": frozenset({"async", "auto", "sync"}),
}


#: Characters that must not appear in URL attribute values because they
#: can obfuscate the scheme (e.g. ``java\tscript:`` bypasses a naive scheme
#: check).  Includes C0/C1 controls, DEL, line/paragraph separators, and
#: common zero-width format characters.
_URL_REJECT_CHARS: re.Pattern[str] = re.compile(
    r"[\x00-\x1f\x7f-\x9f\u2028\u2029\u200b\u200c\u200d\ufeff]"
)


def _is_safe_url(value: str) -> bool:
    """Return True if *value* uses a safe URL scheme or is relative.

    Rejects values containing control, format, or line-separator characters
    *before* scheme checking so that obfuscated schemes like
    ``java\tscript:`` cannot bypass the allowlist.
    """
    if not value or not value.strip():
        return True
    # Reject obfuscation characters before any scheme analysis.
    if _URL_REJECT_CHARS.search(value):
        return False
    stripped = value.strip()
    # Fragment-only links (#section) are safe.
    if stripped.startswith("#"):
        return True
    # Protocol-relative URLs (//example.com) use the page's scheme.
    if stripped.startswith("//"):
        return True
    parsed = urlparse(stripped)
    scheme = parsed.scheme.lower()
    return scheme in _SAFE_SCHEMES


def _clean_attr_value(attr: str, value: str) -> str | None:
    """Return a cleaned attribute value, or None if the attribute is unsafe.

    Strips dangerous URL schemes from URL attributes. Non-URL attributes pass
    through unchanged.
    """
    if attr in _ENUM_ATTR_VALUES:
        normalized = value.strip().lower()
        return normalized if normalized in _ENUM_ATTR_VALUES[attr] else None
    if attr in _URL_ATTRS:
        if not _is_safe_url(value):
            return None
        if attr == "href":
            stripped = value.strip()
            parsed = urlparse(stripped)
            if stripped and not stripped.startswith(("/", "#")) and not parsed.scheme:
                # A bare relative link has no stable base in a static site. Keep
                # the authored text, but do not emit a broken link.
                return None
        return value
    return value


class _SanitizingParser(HTMLParser):
    """HTMLParser that rebuilds HTML with only allowlisted elements/attrs.

    Dangerous elements (script, style, iframe, etc.) and their entire content
    are dropped. Non-allowlisted but non-dangerous elements are unwrapped
    (children kept, tag dropped). Event-handler attributes (``on*``) are always
    removed.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._output: list[str] = []
        # Stack of (tag, is_allowed) for open elements.  When a dangerous
        # element is open, we suppress all content until it closes.
        self._suppress_depth: int = 0

    @property
    def output(self) -> str:
        return "".join(self._output)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()

        # Dangerous void elements (input, embed, meta, link, base, frame)
        # have no reliable closing tag.  Drop the tag itself without entering
        # suppress mode so that following safe siblings and body text survive.
        if tag_lower in _DANGEROUS_VOID_TAGS:
            return

        # Dangerous container elements (script, style, iframe, …) suppress
        # their content until the matching end tag.
        if tag_lower in _DANGEROUS_CONTAINER_TAGS:
            self._suppress_depth += 1
            return

        if self._suppress_depth > 0:
            return

        if tag_lower not in _ALLOWED_TAGS:
            # Unwrap: don't emit the tag, children pass through.
            return

        clean_attrs = self._clean_attrs(tag_lower, attrs)
        attr_str = "".join(
            f' {k}="{html.escape(v, quote=True)}"' for k, v in clean_attrs
        )
        self._output.append(f"<{tag_lower}{attr_str}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle self-closing tags like <img ... />."""
        tag_lower = tag.lower()

        if tag_lower in _DANGEROUS_TAGS:
            return

        if self._suppress_depth > 0:
            return

        if tag_lower not in _ALLOWED_TAGS:
            return

        clean_attrs = self._clean_attrs(tag_lower, attrs)
        attr_str = "".join(
            f' {k}="{html.escape(v, quote=True)}"' for k, v in clean_attrs
        )
        self._output.append(f"<{tag_lower}{attr_str} />")

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()

        # Only dangerous container tags can decrement suppress depth.
        # Void tags never entered suppress mode.
        if tag_lower in _DANGEROUS_CONTAINER_TAGS:
            if self._suppress_depth > 0:
                self._suppress_depth -= 1
            return

        if self._suppress_depth > 0:
            return

        if tag_lower not in _ALLOWED_TAGS:
            return

        self._output.append(f"</{tag_lower}>")

    def handle_data(self, data: str) -> None:
        if self._suppress_depth > 0:
            return
        # HTML-escape decoded text nodes so that entity-decoded content
        # (e.g. ``&lt;script&gt;`` decoded to ``<script>`` by
        # ``convert_charrefs=True``) is re-escaped and cannot inject live
        # tags into the output.
        self._output.append(html.escape(data, quote=False))

    def _clean_attrs(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> list[tuple[str, str]]:
        """Filter attributes to the allowlist and strip dangerous values."""
        allowed = _ALLOWED_ATTRS.get(tag, _ALLOWED_ATTRS["*"])
        result: list[tuple[str, str]] = []
        for name, value in attrs:
            if value is None:
                continue
            name_lower = name.lower()
            # Always reject event-handler attributes.
            if name_lower.startswith("on"):
                continue
            # Check element-specific or global allowlist.
            if name_lower not in allowed:
                continue
            cleaned = _clean_attr_value(name_lower, value)
            if cleaned is not None:
                result.append((name_lower, cleaned))
        if tag == "img":
            present = {name for name, _ in result}
            if "loading" not in present:
                result.append(("loading", "lazy"))
            if "decoding" not in present:
                result.append(("decoding", "async"))
        return result


def sanitize_html(html: str) -> str:
    """Sanitize HTML using an allowlist of safe elements and attributes.

    Preserves normal Markdown-rendered content (paragraphs, headings, lists,
    tables, images, links, blockquotes, emphasis, code) while removing scripts,
    styles, iframes, objects, embeds, forms, event-handler attributes, and
    dangerous URL schemes (``javascript:``, ``data:``, ``vbscript:``).

    Parameters
    ----------
    html:
        Raw HTML string (typically output from a Markdown renderer).

    Returns
    -------
    str
        Sanitized HTML containing only allowlisted elements and attributes.
    """
    if not html:
        return ""
    parser = _SanitizingParser()
    parser.feed(html)
    parser.close()
    return parser.output
