"""HTML5 fragment sanitization after Markdown rendering/front-matter removal.

nh3 owns tree repair and allowlist cleaning. A narrow stdlib token gate rejects
ambiguous dangerous boundaries; a serializer retains existing attribute policy.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from secrets import token_hex
from urllib.parse import urlparse

import nh3

#: Elements that are completely removed (tag, content, and children).
#: These are dangerous embeds, scripting, or interactive elements that
#: are **containers** - their content is cleaned by nh3. Ambiguous source
#: boundaries and frame/frameset markup are rejected before HTML5 tree repair.
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
#: ``base``. Unlike the other void tags, ``frame`` is explicitly rejected.
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


class HTMLSanitizationError(ValueError):
    """A controlled diagnostic containing no authored text or attribute values."""


class _DangerousBoundaryGate(HTMLParser):
    # Do not tokenize example tags inside raw-text/RCDATA elements. This is a
    # lexical rejection gate, not an attempt to reconstruct an HTML5 tree.
    _RAW_TEXT_TAGS = (
        "script",
        "style",
        "iframe",
        "textarea",
        "title",
        "noscript",
        "xmp",
        "noembed",
        "noframes",
    )

    def __init__(self) -> None:
        super().__init__()
        self.opened: list[tuple[str, tuple[int, int]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"frame", "frameset"}:
            raise HTMLSanitizationError(
                f"Unsupported <{tag}> at HTML line {self.getpos()[0]}, column {self.getpos()[1]}"
            )
        if tag in self._RAW_TEXT_TAGS:
            self.set_cdata_mode(tag)
        if not self.opened and tag in _ALLOWED_TAGS:
            for name, value in attrs:
                if value is not None and name in _ALLOWED_ATTRS.get(tag, ()):
                    # nh3 may discard a malformed URL before its callback; keep
                    # the original policy's parse errors observable regardless.
                    _clean_attr_value(name, value)
        # option's end tag is optional; nh3 owns that HTML5 rule.
        if tag in _DANGEROUS_CONTAINER_TAGS - {"option"}:
            self.opened.append((tag, self.getpos()))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _DANGEROUS_CONTAINER_TAGS:
            raise HTMLSanitizationError(
                f"Non-void <{tag}/> at HTML line {self.getpos()[0]}, column {self.getpos()[1]}"
            )
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        # GFM can escape an opening script tag but leave its closing tag. With
        # no dangerous container open, nh3 can safely drop that orphan close.
        if tag in _DANGEROUS_CONTAINER_TAGS - {"option"} and self.opened:
            if self.opened[-1][0] != tag:
                raise HTMLSanitizationError(
                    f"Unmatched </{tag}> at HTML line {self.getpos()[0]}, column {self.getpos()[1]}"
                )
            self.opened.pop()

    def close(self) -> None:
        super().close()
        if self.opened:
            tag, (line, column) = self.opened[-1]
            raise HTMLSanitizationError(
                f"Unclosed <{tag}> at HTML line {line}, column {column}"
            )


class _PolicySerializer(HTMLParser):
    """Serialize only nh3-cleaned HTML, retaining escaping and image defaults."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._output: list[str] = []

    @property
    def output(self) -> str:
        return "".join(self._output)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # nh3's attribute order varies; published artifacts must be deterministic.
        attr_str = "".join(
            f' {k}="{html.escape(v, quote=True)}"'
            for k, v in sorted(self._clean_attrs(tag, attrs))
        )
        self._output.append(f"<{tag}{attr_str}>")

    def handle_endtag(self, tag: str) -> None:
        self._output.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
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
    # HTML5 replaces NUL before callbacks; never turn a rejected URL into an
    # accepted replacement-character URL. Code literals contain escaped markup.
    if "\x00" in html:
        raise HTMLSanitizationError("NUL in HTML fragment")
    gate = _DangerousBoundaryGate()
    gate.feed(html)
    gate.close()
    # ponytail: this bare random token detects only EOF swallowing, not general
    # integrity. Middle-container diagnostics belong to the explicit gate;
    # HTML5 tree safety belongs to nh3. No additional tree parser here.
    marker = token_hex(16)
    errors: list[Exception] = []

    def filter_attribute(tag: str, name: str, value: str) -> str | None:
        # nh3 callbacks cannot propagate exceptions; fail the whole fragment
        # afterwards instead of silently accepting a failed policy check.
        try:
            return _clean_attr_value(name, value)
        except Exception as exc:
            errors.append(exc)
            return None

    cleaned = nh3.clean(
        html + marker,
        tags=_ALLOWED_TAGS,
        clean_content_tags=_DANGEROUS_TAGS,
        attributes=_ALLOWED_ATTRS,
        url_schemes=_SAFE_SCHEMES,
        link_rel=None,
        attribute_filter=filter_attribute,
    )
    if errors:
        raise HTMLSanitizationError("URL/attribute policy failed") from errors[0]
    if marker not in cleaned:
        raise HTMLSanitizationError("HTML parsing discarded or consumed end of body")
    parser = _PolicySerializer()
    parser.feed(cleaned.replace(marker, "", 1))
    parser.close()
    return parser.output
