"""Tests for the Blog-only Atom feed (Ticket 08)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone, tzinfo
from pathlib import Path

import pytest
from pydantic import HttpUrl

from github_blog.atom_feed import (
    AtomFeedBuilder,
    render_atom_xml,
    write_atom_feed,
)
from github_blog.config import (
    AboutConfig,
    GithubConfig,
    SecurityConfig,
    Settings,
    SiteConfig,
)
from github_blog.content_compiler import ContentCompiler
from github_blog.models.atom_feed import AtomEntry, AtomFeed, AtomFeedRoute
from github_blog.models.blog_post import BlogPost
from github_blog.models.issue_snapshot import IssueSnapshot

_ATOM_NS = "http://www.w3.org/2005/Atom"
_DEFAULT_PUB = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)
_DEFAULT_UPD = datetime(2026, 1, 11, 8, 30, tzinfo=timezone.utc)
_BUILD_START = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)

_VALID_BODY = (
    "---\n"
    "slug: my-first-post\n"
    "description: A test post about things.\n"
    'created_date: "2026-01-05"\n'
    "---\n\n"
    "Hello **world**.\n"
)


def _settings(
    *,
    site_title: str = "Test Blog",
    site_author: str = "Test Author",
    site_description: str = "A test site description.",
) -> Settings:
    return Settings(
        github=GithubConfig(repo="user/repo", allowed_authors=["alice"]),
        site=SiteConfig(
            title=site_title,
            url=HttpUrl("https://example.com/"),
            author=site_author,
            description=site_description,
        ),
        about=AboutConfig(issue_number=99),
        security=SecurityConfig(token_env="G_T"),  # noqa: S106
    )


def _post(
    issue_number: int = 1,
    *,
    title: str = "Test Post",
    slug: str = "test-post",
    description: str = "A test post.",
    published_at: datetime = _DEFAULT_PUB,
    updated_at: datetime = _DEFAULT_UPD,
    body_html: str = "<p>Body.</p>",
    canonical_path: str | None = None,
) -> BlogPost:
    return BlogPost(
        issue_number=issue_number,
        title=title,
        slug=slug,
        description=description,
        created_date="2026-01-05",
        published_at=published_at,
        updated_at=updated_at,
        tags=(),
        body_html=body_html,
        canonical_path=canonical_path or f"/blog/{slug}/",
    )


def _snapshot(
    number: int = 1,
    *,
    title: str = "Test Post",
    body: str = _VALID_BODY,
    author: str = "alice",
    labels: tuple[str, ...] = ("type:blog", "published"),
    created_at: datetime = _DEFAULT_PUB,
    updated_at: datetime = _DEFAULT_UPD,
    is_pull_request: bool = False,
) -> IssueSnapshot:
    return IssueSnapshot(
        number=number,
        title=title,
        author=author,
        body=body,
        labels=labels,
        created_at=created_at,
        updated_at=updated_at,
        is_pull_request=is_pull_request,
    )


def _builder(settings: Settings | None = None) -> AtomFeedBuilder:
    return AtomFeedBuilder(settings or _settings(), build_start_time=_BUILD_START)


def _feed(
    *,
    title: str = "Test",
    entries: tuple[AtomEntry, ...] = (),
    updated: datetime = _BUILD_START,
) -> AtomFeed:
    return AtomFeed(
        route=AtomFeedRoute("/atom.xml", "atom.xml"),
        self_url="https://example.com/atom.xml",
        alternate_url="https://example.com/",
        feed_id="https://example.com/",
        title=title,
        subtitle="",
        author_name="Author",
        updated=updated,
        entries=entries,
    )


def test_membership_frontmatter_content() -> None:
    """Compiler -> feed: only published Blog enters; front matter isolated;
    content uses sanitized body_html."""
    valid = _snapshot(number=1, title="Valid Blog")
    unpublished = _snapshot(
        number=2,
        labels=("type:blog",),
        body="---\nslug: x\ndescription: d\ncreated_date: '2026-01-01'\n---\nbody",
    )
    idea = _snapshot(
        number=3,
        labels=("type:idea", "published"),
        body="---\ndescription: d\ncreated_date: '2026-01-01'\n---\nbody",
    )
    unauthorized = _snapshot(number=4, author="eve")
    pr = _snapshot(number=5, is_pull_request=True)

    about = _snapshot(
        number=99,
        labels=("type:about", "published"),
        body='---\ndescription: About\ncreated_date: "2026-01-01"\n---\nabout',
    )
    posts = (
        ContentCompiler(_settings())
        .compile([valid, unpublished, idea, unauthorized, pr, about])
        .blogs
    )
    result = _builder().build(list(posts))

    assert len(result.feed.entries) == 1
    entry = result.feed.entries[0]
    assert entry.title == "Valid Blog"

    # Summary is the validated description only (no front matter).
    assert entry.summary == "A test post about things."
    assert "slug" not in entry.summary and "---" not in entry.summary

    # Content uses sanitized body_html (no script, no front matter).
    assert entry.content_html is not None
    assert "<script" not in entry.content_html.lower()
    assert "Hello" in entry.content_html
    assert "slug:" not in entry.content_html


def test_order_routes_timestamps_xml() -> None:
    """Entry ordering, routes/URLs, timestamps, and valid XML with escaping."""
    same = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)
    p1 = _post(1, published_at=same, title="A & B < C", description="Tom & Jerry")
    p2 = _post(
        2,
        slug="b",
        published_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        title="X & Y",
    )
    p3 = _post(
        3,
        slug="newer",
        published_at=same,
        updated_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
    )
    result = _builder().build([p1, p2, p3])

    # Order: published_at desc, tie-break issue_number desc.
    slugs = [e.link.rstrip("/").rsplit("/", 1)[1] for e in result.feed.entries]
    assert slugs == ["b", "newer", "test-post"]

    # Routes and URLs.
    assert result.feed.route.canonical_path == "/atom.xml"
    assert result.feed.route.output_path == "atom.xml"
    assert result.feed.self_url == "https://example.com/atom.xml"
    assert result.feed.entries[0].id == "https://example.com/blog/b/"
    assert ".html" not in result.feed.entries[0].id

    # Feed-level updated = max entry updated_at.
    assert result.feed.updated == datetime(2026, 1, 20, tzinfo=timezone.utc)

    # Valid XML with escaping.
    xml = render_atom_xml(result.feed)
    assert xml.startswith("<?xml")
    root = ET.fromstring(xml)
    assert root.tag == f"{{{_ATOM_NS}}}feed"
    assert root.findtext(f"{{{_ATOM_NS}}}updated") == "2026-01-20T00:00:00Z"
    # First entry (p2) has escaped title.
    entry = root.find(f"{{{_ATOM_NS}}}entry")
    assert entry is not None
    assert entry.findtext(f"{{{_ATOM_NS}}}title") == "X & Y"
    assert "&amp;" in xml
    self_link = next(
        ln for ln in root.findall(f"{{{_ATOM_NS}}}link") if ln.get("rel") == "self"
    )
    assert self_link.get("type") == "application/atom+xml"


def test_empty_feed_uses_build_start_time() -> None:
    """Empty feed: updated = build_start_time (not now()), valid XML."""
    custom = datetime(2025, 6, 1, 0, 0, tzinfo=timezone.utc)
    result = AtomFeedBuilder(_settings(), build_start_time=custom).build([])
    assert result.feed.updated == custom
    assert not result.has_errors
    assert result.feed.entries == ()
    assert ET.fromstring(render_atom_xml(result.feed)).tag == f"{{{_ATOM_NS}}}feed"


def test_utcoffset_awareness() -> None:
    """Naive datetimes produce diagnostics; utcoffset() semantics (not just
    tzinfo); naive build_start_time has field."""

    class _NullTz(tzinfo):
        def utcoffset(self, dt: datetime | None) -> None:
            return None

        def tzname(self, dt: datetime | None) -> None:
            return None

        def dst(self, dt: datetime | None) -> None:
            return None

    # Both naive -> two diagnostics, post excluded.
    post = _post(
        published_at=datetime(2026, 1, 10, 12, 0),
        updated_at=datetime(2026, 1, 11, 8, 30),
    )
    result = _builder().build([post])
    assert result.has_errors
    fields = {d.field for d in result.diagnostics if d.severity == "error"}
    assert fields == {"published_at", "updated_at"}
    assert result.feed.entries == ()

    # NullTz: tzinfo set but utcoffset() is None -> naive.
    null_post = _post(published_at=datetime(2026, 1, 10, 12, 0, tzinfo=_NullTz()))
    assert _builder().build([null_post]).has_errors

    # Naive build_start_time.
    naive_builder = AtomFeedBuilder(
        _settings(), build_start_time=datetime(2026, 1, 15, 9, 0)
    )
    naive_result = naive_builder.build([])
    assert naive_result.has_errors
    assert any(
        d.field == "build_start_time"
        for d in naive_result.diagnostics
        if d.severity == "error"
    )


def test_xml1_0_invalid_char_builder_and_renderer() -> None:
    """U+0001 in site fields and post fields produces diagnostics and
    excludes entries; renderer raises AtomXmlError (ValueError)."""
    # Site-level invalid chars.
    settings = _settings(
        site_title="Bad\x01Title",
        site_author="Bad\x01Author",
        site_description="Bad\x01Desc",
    )
    result = AtomFeedBuilder(settings, build_start_time=_BUILD_START).build([])
    assert result.has_errors
    assert {
        d.field for d in result.diagnostics if d.code == "ATOM_XML_INVALID_CHAR"
    } == {"title", "author_name", "subtitle"}

    # Post-level invalid chars exclude entries; valid entry unaffected.
    valid = _post(1, title="Good")
    bad_title = _post(2, slug="bt", title="Bad\x01")
    bad_body = _post(3, slug="bb", body_html="<p>Bad\x01body</p>")
    result = _builder().build([valid, bad_title, bad_body])
    assert result.has_errors
    assert len(result.feed.entries) == 1
    assert result.feed.entries[0].title == "Good"
    bad_issues = {
        d.issue_number for d in result.diagnostics if d.code == "ATOM_XML_INVALID_CHAR"
    }
    assert bad_issues == {2, 3}

    # Renderer defense-in-depth raises ValueError.
    entry = AtomEntry(
        id="https://example.com/blog/x/",
        title="Title",
        link="https://example.com/blog/x/",
        summary="Summary",
        published=_DEFAULT_PUB,
        updated=_DEFAULT_UPD,
        content_html="<p>Bad\x01body</p>",
    )
    with pytest.raises(ValueError, match=r"illegal XML 1\.0"):
        render_atom_xml(_feed(entries=(entry,)))

    # Feed-level title also raises.
    with pytest.raises(ValueError, match=r"illegal XML 1\.0"):
        render_atom_xml(_feed(title="Bad\x01Title"))


def test_normal_unicode_valid() -> None:
    """Normal Unicode, newlines, tabs, and CR are valid XML 1.0."""
    post = _post(
        title="Café - 中文标题",
        description="Emoji 😀 and Unicode ♠",
        body_html="<p>Line1\nLine2\tTab\rCR</p>",
    )
    result = _builder().build([post])
    assert not result.has_errors
    root = ET.fromstring(render_atom_xml(result.feed))
    assert (
        root.findtext(f"{{{_ATOM_NS}}}entry/{{{_ATOM_NS}}}title") == "Café - 中文标题"
    )


def test_compiler_to_builder_to_renderer_to_writer_tracer(tmp_path: Path) -> None:
    """Full pipeline tracer: compiler -> builder -> renderer -> writer."""
    about = _snapshot(
        number=99,
        labels=("type:about", "published"),
        body='---\ndescription: About\ncreated_date: "2026-01-01"\n---\nabout',
    )
    post = ContentCompiler(_settings()).compile([_snapshot(), about]).blogs[0]
    result = _builder().build([post])

    xml = render_atom_xml(result.feed)
    root = ET.fromstring(xml)
    assert root.tag == f"{{{_ATOM_NS}}}feed"
    assert root.findtext(f"{{{_ATOM_NS}}}entry/{{{_ATOM_NS}}}title") == "Test Post"

    path = write_atom_feed(result.feed, render_atom_xml, tmp_path)
    assert path == tmp_path / "atom.xml"
    assert path.exists()
    assert path.read_text(encoding="utf-8").startswith("<?xml")
