"""Tests for the Blog-only Atom feed (Ticket 08).

Minimal high-value test set covering:
- Compiler -> feed membership + front-matter isolation
- Ordering, tie-breaking, timestamps, feed-level updated
- Empty feed build-start time
- Route, self/entry URLs, valid XML, escaping
- Timezone diagnostics accumulation (utcoffset() semantics)
- XML 1.0 invalid character builder + renderer defense
- Writer output path
- No CLI cutover (static regression)

Simplification principles applied:
- One test per behavioral concern, not one per dataclass field.
- No mechanical per-field expansion: site title/author/description and
  post title/body/description are validated by the same code path, so a
  representative subset is tested rather than every field individually.
- Implementation details (immutability, exact diagnostic message text)
  are not tested unless they are part of the contract.
"""

from __future__ import annotations

import inspect
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
from github_blog.blog_compiler import BlogCompiler
from github_blog.config import (
    AboutConfig,
    GithubConfig,
    SecurityConfig,
    Settings,
    SiteConfig,
)
from github_blog.models.atom_feed import (
    AtomEntry,
    AtomFeed,
    AtomFeedRoute,
)
from github_blog.models.blog_post import BlogPost
from github_blog.models.issue_snapshot import IssueSnapshot

# ---------------------------------------------------------------------------
# Constants and helpers
# ---------------------------------------------------------------------------

_ATOM_NS = "http://www.w3.org/2005/Atom"

_DEFAULT_PUBLISHED = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)
_DEFAULT_UPDATED = datetime(2026, 1, 11, 8, 30, tzinfo=timezone.utc)
_BUILD_START = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)

_VALID_BODY = (
    "---\n"
    "slug: my-first-post\n"
    "description: A test post about things.\n"
    'created_date: "2026-01-05"\n'
    "---\n\n"
    "Hello **world**.\n"
)


def _make_settings(
    *,
    site_title: str = "Test Blog",
    site_author: str = "Test Author",
    site_description: str = "A test site description.",
) -> Settings:
    return Settings(
        github=GithubConfig(
            repo="user/repo",
            allowed_authors=["alice"],
        ),
        site=SiteConfig(
            title=site_title,
            url=HttpUrl("https://example.com/"),
            author=site_author,
            description=site_description,
        ),
        about=AboutConfig(issue_number=1),
        security=SecurityConfig(token_env="G_T"),  # noqa: S106
    )


def _make_blog_post(
    issue_number: int = 1,
    title: str = "Test Post",
    slug: str = "test-post",
    description: str = "A test post.",
    published_at: datetime = _DEFAULT_PUBLISHED,
    updated_at: datetime = _DEFAULT_UPDATED,
    body_html: str = "<p>Body.</p>",
    canonical_path: str | None = None,
) -> BlogPost:
    if canonical_path is None:
        canonical_path = f"/blog/{slug}/"
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
        canonical_path=canonical_path,
    )


def _make_snapshot(
    number: int = 1,
    *,
    title: str = "Test Post",
    body: str = _VALID_BODY,
    author: str = "alice",
    labels: tuple[str, ...] = ("type:blog", "published"),
    created_at: datetime = _DEFAULT_PUBLISHED,
    updated_at: datetime = _DEFAULT_UPDATED,
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


def _make_builder(settings: Settings | None = None) -> AtomFeedBuilder:
    return AtomFeedBuilder(
        settings or _make_settings(),
        build_start_time=_BUILD_START,
    )


def _make_feed(
    *,
    title: str = "Test",
    subtitle: str = "",
    author_name: str = "Author",
    entries: tuple[AtomEntry, ...] = (),
    updated: datetime = _BUILD_START,
) -> AtomFeed:
    return AtomFeed(
        route=AtomFeedRoute("/atom.xml", "atom.xml"),
        self_url="https://example.com/atom.xml",
        alternate_url="https://example.com/",
        feed_id="https://example.com/",
        title=title,
        subtitle=subtitle,
        author_name=author_name,
        updated=updated,
        entries=entries,
    )


# ===========================================================================
# 1. Membership + front-matter isolation
# ===========================================================================


class TestMembershipAndFrontmatter:
    """Compiler -> feed: only published Blog enters; front matter isolated."""

    def test_only_published_blog_enters_feed(self) -> None:
        """Mixed snapshots: only the valid published Blog enters the feed;
        unpublished, Idea, About, unauthorized, and PR are excluded."""
        valid_blog = _make_snapshot(number=1, title="Valid Blog")
        unpublished = _make_snapshot(
            number=2,
            labels=("type:blog",),
            body="---\nslug: x\ndescription: d\ncreated_date: '2026-01-01'\n---\nbody",
        )
        idea = _make_snapshot(
            number=3,
            labels=("type:idea", "published"),
            body="---\ndescription: d\ncreated_date: '2026-01-01'\n---\nbody",
        )
        unauthorized = _make_snapshot(number=4, author="eve")
        pr = _make_snapshot(number=5, is_pull_request=True)

        posts = (
            BlogCompiler(_make_settings())
            .compile([valid_blog, unpublished, idea, unauthorized, pr])
            .posts
        )
        result = _make_builder().build(list(posts))
        assert len(result.feed.entries) == 1
        assert result.feed.entries[0].title == "Valid Blog"

    def test_summary_has_no_frontmatter(self) -> None:
        """The feed summary is the validated description only."""
        body = (
            "---\n"
            "slug: integration-post\n"
            "description: Clean validated summary.\n"
            'created_date: "2026-01-05"\n'
            "---\n\n"
            "This is the body content."
        )
        post = (
            BlogCompiler(_make_settings()).compile([_make_snapshot(body=body)]).posts[0]
        )
        summary = _make_builder().build([post]).feed.entries[0].summary
        assert summary == "Clean validated summary."
        assert "slug" not in summary
        assert "---" not in summary
        assert "This is the body content." not in summary


# ===========================================================================
# 2. Ordering, tie-breaking, timestamps, feed-level updated
# ===========================================================================


class TestOrderingAndTimestamps:
    """Entry ordering, timestamps, and feed-level updated."""

    def test_ordering_published_desc_with_tie_break(self) -> None:
        """Entries sort by published_at desc; ties break by issue_number desc."""
        same_time = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)
        p1 = _make_blog_post(issue_number=1, published_at=same_time)
        p2 = _make_blog_post(issue_number=2, slug="b", published_at=same_time)
        p3 = _make_blog_post(
            issue_number=3,
            slug="newer",
            published_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        result = _make_builder().build([p1, p2, p3])
        slugs = [e.link.rstrip("/").rsplit("/", 1)[1] for e in result.feed.entries]
        assert slugs == ["newer", "b", "test-post"]

    def test_entry_timestamps_and_feed_updated(self) -> None:
        """published = Issue created_at, updated = Issue updated_at;
        feed-level updated = max entry updated_at."""
        p1 = _make_blog_post(
            issue_number=1,
            published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
        )
        p2 = _make_blog_post(
            issue_number=2,
            slug="b",
            published_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 1, 20, tzinfo=timezone.utc),
        )
        result = _make_builder().build([p1, p2])
        entry = result.feed.entries[0]
        assert entry.published == datetime(2026, 2, 1, tzinfo=timezone.utc)
        assert entry.updated == datetime(2026, 1, 20, tzinfo=timezone.utc)
        assert result.feed.updated == datetime(2026, 1, 20, tzinfo=timezone.utc)

        root = ET.fromstring(render_atom_xml(result.feed))
        assert root.findtext(f"{{{_ATOM_NS}}}updated") == "2026-01-20T00:00:00Z"
        rendered_entry = root.find(f"{{{_ATOM_NS}}}entry")
        assert rendered_entry is not None
        assert rendered_entry.findtext(f"{{{_ATOM_NS}}}published") == (
            "2026-02-01T00:00:00Z"
        )
        assert rendered_entry.findtext(f"{{{_ATOM_NS}}}updated") == (
            "2026-01-20T00:00:00Z"
        )


# ===========================================================================
# 3. Empty feed: build_start_time
# ===========================================================================


class TestEmptyFeedBuildStart:
    """Empty feed uses explicitly injected build_start_time."""

    def test_empty_feed_uses_build_start_and_is_valid(self) -> None:
        """Empty feed: updated = build_start_time (explicitly injected, not
        now()), no errors, and the rendered XML is valid."""
        custom_start = datetime(2025, 6, 1, 0, 0, tzinfo=timezone.utc)
        result = AtomFeedBuilder(_make_settings(), build_start_time=custom_start).build(
            []
        )
        assert result.feed.updated == custom_start
        assert not result.has_errors
        assert result.feed.entries == ()
        xml = render_atom_xml(result.feed)
        assert ET.fromstring(xml).tag == f"{{{_ATOM_NS}}}feed"


# ===========================================================================
# 4. Route, self/entry URLs, valid XML, escaping
# ===========================================================================


class TestRouteAndValidXml:
    """Route, self/entry URLs, valid XML with escaping."""

    def test_route_self_and_entry_urls(self) -> None:
        """Route is /atom.xml -> atom.xml; self URL from origin; entry
        id/link from canonical_path (not .html or issue-number routes)."""
        post = _make_blog_post(issue_number=42, slug="my-slug")
        result = _make_builder().build([post])
        assert result.feed.route.canonical_path == "/atom.xml"
        assert result.feed.route.output_path == "atom.xml"
        assert result.feed.self_url == "https://example.com/atom.xml"
        entry = result.feed.entries[0]
        assert entry.id == "https://example.com/blog/my-slug/"
        assert entry.link == entry.id
        assert ".html" not in entry.id
        assert "/42" not in entry.id

        root = ET.fromstring(render_atom_xml(result.feed))
        links = root.findall(f"{{{_ATOM_NS}}}link")
        self_link = next(link for link in links if link.get("rel") == "self")
        assert self_link.get("href") == "https://example.com/atom.xml"
        assert self_link.get("type") == "application/atom+xml"
        rendered_entry = root.find(f"{{{_ATOM_NS}}}entry")
        assert rendered_entry is not None
        entry_link = rendered_entry.find(f"{{{_ATOM_NS}}}link")
        assert entry_link is not None
        assert entry_link.get("href") == "https://example.com/blog/my-slug/"

    def test_valid_xml_with_escaping(self) -> None:
        """Rendered XML has declaration, Atom namespace, and properly
        escaped special characters; parses without error."""
        post = _make_blog_post(
            title="A & B < C",
            description="Tom & Jerry",
            body_html="<p>Hello &amp; world</p>",
        )
        xml = render_atom_xml(_make_builder().build([post]).feed)
        assert xml.startswith("<?xml")
        root = ET.fromstring(xml)
        assert root.tag == f"{{{_ATOM_NS}}}feed"
        entry = root.find(f"{{{_ATOM_NS}}}entry")
        assert entry is not None
        title = entry.find(f"{{{_ATOM_NS}}}title")
        assert title is not None
        assert title.text == "A & B < C"
        summary = entry.find(f"{{{_ATOM_NS}}}summary")
        assert summary is not None
        assert summary.text == "Tom & Jerry"
        assert "&amp;" in xml
        assert "&lt;" in xml


# ===========================================================================
# 5. Timezone diagnostics: utcoffset() semantics
# ===========================================================================


class TestTimezoneDiagnostics:
    """Timezone-awareness diagnostics with utcoffset() semantics."""

    def test_both_naive_produces_two_diagnostics_with_fields(self) -> None:
        """When both published_at and updated_at are naive, two independent
        diagnostics are accumulated (no first-continue), each with the
        correct field name; the post is excluded and has_errors is True."""
        post = _make_blog_post(
            published_at=datetime(2026, 1, 10, 12, 0),  # naive
            updated_at=datetime(2026, 1, 11, 8, 30),  # naive
        )
        result = _make_builder().build([post])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        assert len(errors) == 2
        assert {d.field for d in errors} == {"published_at", "updated_at"}
        assert result.feed.entries == ()

    def test_utcoffset_semantics_not_just_tzinfo(self) -> None:
        """A datetime whose tzinfo is set but utcoffset() returns None
        (or raises) is treated as naive per Python semantics."""

        class _NullTz(tzinfo):
            def utcoffset(self, dt: datetime | None) -> None:
                return None

            def tzname(self, dt: datetime | None) -> None:
                return None

            def dst(self, dt: datetime | None) -> None:
                return None

        class _ExplodingTz(tzinfo):
            def utcoffset(self, dt: datetime | None) -> None:
                raise RuntimeError("boom")

            def tzname(self, dt: datetime | None) -> None:
                return None

            def dst(self, dt: datetime | None) -> None:
                return None

        # NullTz: tzinfo is set, utcoffset() is None -> naive
        post_null = _make_blog_post(
            published_at=datetime(2026, 1, 10, 12, 0, tzinfo=_NullTz()),
        )
        result_null = _make_builder().build([post_null])
        assert result_null.has_errors
        assert result_null.diagnostics[0].field == "published_at"

        # ExplodingTz: utcoffset() raises -> safely treated as naive
        post_explode = _make_blog_post(
            published_at=datetime(2026, 1, 10, 12, 0, tzinfo=_ExplodingTz()),
        )
        result_explode = _make_builder().build([post_explode])
        assert result_explode.has_errors

    def test_naive_build_start_has_field(self) -> None:
        """Naive build_start_time produces an error with field='build_start_time'."""
        builder = AtomFeedBuilder(
            _make_settings(),
            build_start_time=datetime(2026, 1, 15, 9, 0),  # naive
        )
        result = builder.build([])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        assert len(errors) == 1
        assert errors[0].field == "build_start_time"


# ===========================================================================
# 6. XML 1.0 invalid character validation
# ===========================================================================


class TestXmlCharValidation:
    """XML 1.0 illegal control characters are detected and rejected."""

    def test_u0001_in_site_fields_produces_errors(self) -> None:
        """U+0001 in site title, author, and description each produce an
        error diagnostic with the correct field name."""
        settings = _make_settings(
            site_title="Bad\x01Title",
            site_author="Bad\x01Author",
            site_description="Bad\x01Desc",
        )
        result = AtomFeedBuilder(settings, build_start_time=_BUILD_START).build([])
        assert result.has_errors
        fields = {
            d.field
            for d in result.diagnostics
            if d.severity == "error" and d.code == "ATOM_XML_INVALID_CHAR"
        }
        assert fields == {"title", "author_name", "subtitle"}

    def test_u0001_in_post_fields_excludes_entry(self) -> None:
        """U+0001 in post title or body excludes the entry; a valid entry
        in the same build is unaffected."""
        valid = _make_blog_post(issue_number=1, title="Good")
        bad_title = _make_blog_post(issue_number=2, slug="bt", title="Bad\x01")
        bad_body = _make_blog_post(
            issue_number=3, slug="bb", body_html="<p>Bad\x01body</p>"
        )
        result = _make_builder().build([valid, bad_title, bad_body])
        assert result.has_errors
        assert len(result.feed.entries) == 1
        assert result.feed.entries[0].title == "Good"
        bad_issues = {
            d.issue_number
            for d in result.diagnostics
            if d.severity == "error" and d.code == "ATOM_XML_INVALID_CHAR"
        }
        assert bad_issues == {2, 3}

    def test_normal_unicode_and_whitespace_valid(self) -> None:
        """Normal Unicode, newlines, tabs, and CR are all valid XML 1.0."""
        post = _make_blog_post(
            title="Café - 中文标题",
            description="Emoji 😀 and Unicode ♠",
            body_html="<p>Line1\nLine2\tTab\rCR</p>",
        )
        result = _make_builder().build([post])
        assert not result.has_errors
        assert len(result.feed.entries) == 1
        root = ET.fromstring(render_atom_xml(result.feed))
        assert root.findtext(f"{{{_ATOM_NS}}}entry/{{{_ATOM_NS}}}title") == (
            "Café - 中文标题"
        )

    def test_renderer_raises_on_illegal_char(self) -> None:
        """Defense-in-depth: the renderer raises ValueError (AtomXmlError)
        when any field contains an illegal XML 1.0 character."""
        entry = AtomEntry(
            id="https://example.com/blog/x/",
            title="Title",
            link="https://example.com/blog/x/",
            summary="Summary",
            published=_DEFAULT_PUBLISHED,
            updated=_DEFAULT_UPDATED,
            content_html="<p>Bad\x01body</p>",
        )
        feed = _make_feed(entries=(entry,))
        with pytest.raises(ValueError, match=r"illegal XML 1\.0"):
            render_atom_xml(feed)

    def test_renderer_raises_on_illegal_char_in_feed_title(self) -> None:
        """Defense-in-depth: illegal char in feed-level title also raises."""
        feed = _make_feed(title="Bad\x01Title")
        with pytest.raises(ValueError, match=r"illegal XML 1\.0"):
            render_atom_xml(feed)


# ===========================================================================
# 7. Writer output path
# ===========================================================================


class TestWriterOutput:
    """write_atom_feed writes to route.output_path only."""

    def test_writer_uses_route_output_path(self, tmp_path: Path) -> None:
        result = _make_builder().build([])
        path = write_atom_feed(result.feed, render_atom_xml, tmp_path)
        assert path == tmp_path / "atom.xml"
        assert path.exists()
        assert path.read_text(encoding="utf-8").startswith("<?xml")


# ===========================================================================
# 8. Content from sanitized body
# ===========================================================================


class TestContentFromCompiler:
    """Content element uses the sanitized body_html from BlogCompiler."""

    def test_content_uses_sanitized_body(self) -> None:
        """Content comes from the compiler's sanitized body_html, not the
        raw Issue body; scripts are removed, front matter is absent."""
        body = (
            "---\n"
            "slug: content-test\n"
            "description: A post.\n"
            'created_date: "2026-01-05"\n'
            "---\n\n"
            "<script>alert(1)</script>\n\nNormal **text**."
        )
        post = (
            BlogCompiler(_make_settings()).compile([_make_snapshot(body=body)]).posts[0]
        )
        content_html = _make_builder().build([post]).feed.entries[0].content_html
        assert content_html is not None
        assert "<script" not in content_html.lower()
        assert "Normal" in content_html
        assert "slug:" not in content_html
        assert "---" not in content_html


# ===========================================================================
# 9. No CLI cutover (static regression)
# ===========================================================================


class TestNoCliCutover:
    """The strict Atom builder remains a tracer; the default CLI uses
    legacy RenderService.generate_rss, not AtomFeedBuilder."""

    def test_atom_feed_not_used_by_cli(self) -> None:
        from github_blog import cli

        source = inspect.getsource(cli)
        assert "AtomFeedBuilder" not in source
        assert "render_atom_xml" not in source
