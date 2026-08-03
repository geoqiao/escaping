from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import pytest

from escaping.atom_feed import AtomXmlError, render_atom_xml
from escaping.models.atom_feed import AtomEntry, AtomFeed
from escaping.models.site import (
    BrandingMetadata,
    CommentsMetadata,
    SiteMetadata,
    SiteProfile,
    ThemeMetadata,
)
from escaping.routes import RouteRegistry

_ATOM_NS = "http://www.w3.org/2005/Atom"
_AWARE = datetime(2026, 1, 2, tzinfo=timezone.utc)


def _metadata(*, title: str = "Test & Notes") -> SiteMetadata:
    return SiteMetadata(
        title=title,
        author="Owner",
        description="A site description.",
        language="en",
        github_name="owner",
        github_repo="owner/site",
        navigation=(),
        profile=SiteProfile(),
        branding=BrandingMetadata(True, "Powered by", "https://example.com/", ""),
        comments=CommentsMetadata("owner/site", "github-light", "auto"),
        google_search_verification="",
        theme=ThemeMetadata(
            "geoqiao.me",
            "/templates/geoqiao.me",
            "https://example.com/templates/geoqiao.me/static/images/favicon.png",
        ),
    )


def _entry(*, content_html: str = "<p>Body &amp; more.</p>") -> AtomEntry:
    url = "https://example.com/blog/post/"
    return AtomEntry(
        id=url,
        title="Café & 中文",
        link=url,
        summary="Summary & details",
        published=_AWARE,
        updated=_AWARE,
        content_html=content_html,
    )


def _feed(*, updated: datetime = _AWARE, entry: AtomEntry | None = None) -> AtomFeed:
    route = RouteRegistry("https://example.com/").atom()
    return AtomFeed(route=route, updated=updated, entries=((entry or _entry()),))


def test_atom_renderer_uses_metadata_routes_and_escapes_xml() -> None:
    xml = render_atom_xml(_feed(), _metadata(), "https://example.com/")
    root = ET.fromstring(xml)

    assert root.findtext(f"{{{_ATOM_NS}}}id") == "https://example.com/"
    assert root.findtext(f"{{{_ATOM_NS}}}title") == "Test & Notes"
    assert root.findtext(f"{{{_ATOM_NS}}}author/{{{_ATOM_NS}}}name") == "Owner"
    self_link = next(
        link
        for link in root.findall(f"{{{_ATOM_NS}}}link")
        if link.attrib.get("rel") == "self"
    )
    assert self_link.attrib["href"] == "https://example.com/atom.xml"
    assert root.findtext(f"{{{_ATOM_NS}}}entry/{{{_ATOM_NS}}}title") == "Café & 中文"
    assert "&amp;" in xml


def test_atom_renderer_rejects_illegal_xml_characters() -> None:
    with pytest.raises(AtomXmlError, match=r"illegal XML 1\.0"):
        render_atom_xml(
            _feed(), _metadata(title="Bad\x01Title"), "https://example.com/"
        )

    with pytest.raises(AtomXmlError, match=r"illegal XML 1\.0"):
        render_atom_xml(
            _feed(entry=_entry(content_html="<p>Bad\x01Body</p>")),
            _metadata(),
            "https://example.com/",
        )


def test_atom_renderer_rejects_naive_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        render_atom_xml(
            _feed(updated=datetime(2026, 1, 2)),
            _metadata(),
            "https://example.com/",
        )
