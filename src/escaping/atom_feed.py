"""Render atom.xml, the Blog's Atom feed (RFC 4287)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from .models.blog_post import blog_post_sort_key

if TYPE_CHECKING:
    from .models.site import SiteModel

_NS = "http://www.w3.org/2005/Atom"
ET.register_namespace("", _NS)

# Characters XML 1.0 forbids. The Config and every Blog post are checked for
# them, so they reach the feed only through a bug.
NOT_XML = re.compile("[^\t\n\r\x20-퟿-�\U00010000-\U0010ffff]")


def _add(
    parent: ET.Element, tag: str, text: str | None = None, **attrs: str
) -> ET.Element:
    child = ET.SubElement(parent, f"{{{_NS}}}{tag}", attrs)
    child.text = text
    return child


def _time(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def render_atom_xml(site: SiteModel) -> str:
    """Every Blog post, newest first.

    The feed's time is the latest post update, or the build's start when the
    Blog is empty.
    """
    metadata = site.metadata
    home = site.routes.route("home").canonical_url
    feed = ET.Element(f"{{{_NS}}}feed")
    _add(feed, "id", home)
    _add(feed, "title", metadata.title)
    self_url = site.routes.route("atom").canonical_url
    _add(feed, "link", rel="self", type="application/atom+xml", href=self_url)
    _add(feed, "link", rel="alternate", type="text/html", href=home)
    _add(_add(feed, "author"), "name", metadata.author)
    if metadata.description:
        _add(feed, "subtitle", metadata.description)
    posts = sorted(site.blogs, key=blog_post_sort_key, reverse=True)
    updated = max((post.updated_at for post in posts), default=site.build_start_time)
    _add(feed, "updated", _time(updated))
    for post in posts:
        url = post.route.canonical_url
        entry = _add(feed, "entry")
        _add(entry, "id", url)
        _add(entry, "title", post.title)
        _add(entry, "link", rel="alternate", type="text/html", href=url)
        _add(entry, "summary", post.description)
        _add(entry, "published", _time(post.published_at))
        _add(entry, "updated", _time(post.updated_at))
        _add(entry, "content", post.body_html, type="html")
    xml = ET.tostring(feed, encoding="utf-8", xml_declaration=True).decode("utf-8")
    if match := NOT_XML.search(xml):
        raise ValueError(
            f"atom.xml would contain U+{ord(match.group()):04X}, "
            "a character XML 1.0 forbids"
        )
    return xml
