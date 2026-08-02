"""Tests for the Blog tag taxonomy (Ticket 07)."""

from __future__ import annotations

import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import HttpUrl

from github_blog.config import (
    AboutConfig,
    GithubConfig,
    SecurityConfig,
    Settings,
    SiteConfig,
)
from github_blog.models.blog_post import BlogPost, BlogTag
from github_blog.models.tag_taxonomy import (
    TagArchive,
    TagArchiveEntry,
    TagArchiveRoute,
    TagsIndex,
    TagsIndexRoute,
    TagSummary,
)
from github_blog.services.render_service import RenderService
from github_blog.tag_taxonomy import (
    TagTaxonomyBuilder,
    write_tag_archives,
    write_tag_index,
)

_PROJECT_ROOT = Path(__file__).parent.parent.absolute()
_DEFAULT_PUB = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)
_DEFAULT_UPD = datetime(2026, 1, 11, 8, 30, tzinfo=timezone.utc)


def _settings() -> Settings:
    return Settings(
        github=GithubConfig(repo="user/repo", allowed_authors=["alice"]),
        site=SiteConfig(
            title="Test Blog",
            url=HttpUrl("https://example.com/"),
            author="Test",
        ),
        about=AboutConfig(issue_number=1),
        security=SecurityConfig(token_env="G_T"),  # noqa: S106
    )


def _tag(name: str) -> BlogTag:
    key = unicodedata.normalize("NFC", name).casefold()
    return BlogTag(name=name, path=f"/tags/{key}/")


def _post(
    issue_number: int = 1,
    *,
    title: str = "Test Post",
    slug: str = "test-post",
    tags: tuple[BlogTag, ...] = (),
    published_at: datetime = _DEFAULT_PUB,
) -> BlogPost:
    return BlogPost(
        issue_number=issue_number,
        title=title,
        slug=slug,
        description="A test post.",
        created_date="2026-01-05",
        published_at=published_at,
        updated_at=_DEFAULT_UPD,
        tags=tags,
        body_html="<p>Body.</p>",
        canonical_path=f"/blog/{slug}/",
    )


def _render_service(theme: str = "Escape1") -> RenderService:
    settings = MagicMock()
    settings.paths.theme_path = _PROJECT_ROOT / "templates" / theme
    settings.paths.seo_path = _PROJECT_ROOT / "templates" / "seo"
    settings.paths.theme_url_path = f"/templates/{theme}"
    settings.paths.rss = "atom.xml"
    settings.paths.blog = "blog"
    settings.paths.tag = "tag"
    settings.paths.page = "page"
    settings.site.title = "Test Blog"
    settings.site.url = "https://example.com/"
    settings.site.author = "Author"
    settings.site.description = "Test Description"
    settings.site.language = "en"
    settings.github.username = "user"
    settings.github.repo = "user/repo"
    settings.seo.google_search_console = ""
    settings.profile.avatar = ""
    settings.profile.bio = "Test bio"
    settings.profile.links = []
    settings.site.navigation.items = []
    settings.branding.show_powered_by = True
    settings.branding.powered_by_text = "Powered by"
    settings.branding.powered_by_url = "https://github.com/geoqiao/github-blog"
    settings.branding.show_intro = False
    settings.branding.intro_text = ""
    settings.branding.intro_text2 = (
        "Generated with Python + Jinja2, deployed via GitHub Actions."
    )
    settings.branding.source_link_text = "View Source"
    settings.branding.source_link_url = ""
    settings.comments.provider = "utterances"
    settings.comments.repo = ""
    settings.comments.theme = "github-light"
    settings.comments.theme_mode = "auto"
    return RenderService(settings)


def _mock_issue(
    number: int = 1,
    *,
    title: str = "Test Post",
    labels: list[str] | None = None,
) -> Any:  # noqa: ANN401
    issue = MagicMock()
    issue.number = number
    issue.title = title
    issue.body = "body"
    label_mocks = []
    if labels:
        for label in labels:
            m = MagicMock()
            m.name = label
            label_mocks.append(m)
    issue.labels = label_mocks
    issue.created_at = datetime(2024, 1, number, tzinfo=timezone.utc)
    issue.updated_at = datetime(2024, 1, number, tzinfo=timezone.utc)
    return issue


def test_nfc_casefold_samepost_dedup_count() -> None:
    """NFC + casefold dedup, same-post duplicates counted once, count
    aggregation across posts, deterministic display/order."""
    # NFC equivalence: composed vs decomposed "café".
    composed = "café"
    decomposed = "cafe\u0301"
    # Casefold: "Python" == "python" == "PYTHON".
    p1 = _post(1, tags=(BlogTag(name="Python", path="/tags/python/"),))
    p2 = _post(
        2,
        slug="b",
        tags=(
            BlogTag(name="PYTHON", path="/tags/python/"),
            BlogTag(name="python", path="/tags/python/"),  # same-post dup
        ),
    )
    p3 = _post(
        3,
        slug="c",
        tags=(
            BlogTag(name=composed, path="/tags/café/"),
            BlogTag(name=decomposed, path="/tags/café/"),  # NFC-equivalent dup
        ),
    )
    result = TagTaxonomyBuilder(_settings()).build([p1, p2, p3])

    # Two unique tags after dedup, sorted alphabetically by key.
    names = [t.name for t in result.index.tags]
    assert names == ["café", "python"]

    # python: p1 + p2 (p2 counted once despite duplicate within post).
    assert result.index.tags[1].count == 2
    # café: p3 only (counted once).
    assert result.index.tags[0].count == 1

    # Display value is the NFC+casefold key (deterministic).
    assert result.index.tags[1].name == "python"

    # Archive for python has 2 entries, sorted desc by publication.
    py_archive = next(a for a in result.archives if a.tag_name == "python")
    assert len(py_archive.entries) == 2
    assert py_archive.entries[0].title == "Test Post"  # issue 1 (same ts, higher num)

    # No collisions under normal operation.
    assert not result.has_errors


def test_archive_order_routes_empty() -> None:
    """Archive entries sorted desc, routes pre-computed, empty state
    produces index with no archives."""
    p_old = _post(
        1,
        slug="old",
        title="Old",
        tags=(_tag("python"),),
        published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    p_new = _post(
        2,
        slug="new",
        title="New",
        tags=(_tag("python"),),
        published_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    result = TagTaxonomyBuilder(_settings()).build([p_old, p_new])

    # Archive order desc.
    archive = result.archives[0]
    assert [e.title for e in archive.entries] == ["New", "Old"]

    # Routes.
    assert result.index.route.canonical_path == "/tags/"
    assert result.index.route.output_path == "tags/index.html"
    assert result.index.canonical_url == "https://example.com/tags/"
    assert archive.route.canonical_path == "/tags/python/"
    assert archive.route.output_path == "tags/python/index.html"
    assert archive.canonical_url == "https://example.com/tags/python/"
    assert archive.entries[0].detail_path == "/blog/new/"
    assert archive.index_route.canonical_path == "/tags/"

    # Empty state.
    empty = TagTaxonomyBuilder(_settings()).build([])
    assert empty.index.route.canonical_path == "/tags/"
    assert empty.index.tags == ()
    assert empty.archives == ()


@pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
def test_theme_renderer_and_writers_tracer(theme: str, tmp_path: Path) -> None:
    """Strict renderer consumes internal models; writer tracers write to
    pre-computed output paths."""
    render = _render_service(theme)
    index = TagsIndex(
        route=TagsIndexRoute(canonical_path="/tags/", output_path="tags/index.html"),
        canonical_url="https://example.com/tags/",
        tags=(
            TagSummary(
                name="python",
                count=3,
                route=TagArchiveRoute(
                    canonical_path="/tags/python/",
                    output_path="tags/python/index.html",
                ),
            ),
        ),
    )
    archive = TagArchive(
        route=TagArchiveRoute(
            canonical_path="/tags/python/",
            output_path="tags/python/index.html",
        ),
        canonical_url="https://example.com/tags/python/",
        tag_name="python",
        index_route=TagsIndexRoute(
            canonical_path="/tags/", output_path="tags/index.html"
        ),
        entries=(
            TagArchiveEntry(
                title="My Post",
                created_date="2026-01-05",
                detail_path="/blog/my-post/",
                tags=(_tag("python"),),
            ),
        ),
    )

    idx_html = render.render_tag_index(index)
    assert "python" in idx_html
    assert 'href="/tags/python/"' in idx_html
    assert "https://example.com/tags/" in idx_html

    arc_html = render.render_tag_archive(archive)
    assert "My Post" in arc_html
    assert 'href="/blog/my-post/"' in arc_html
    assert "https://example.com/tags/python/" in arc_html
    # Strict archive must not produce .html detail links.
    assert "/blog/my-post.html" not in arc_html

    # Empty index renders intentional state.
    empty_html = render.render_tag_index(
        TagsIndex(
            route=TagsIndexRoute(
                canonical_path="/tags/", output_path="tags/index.html"
            ),
            canonical_url="https://example.com/tags/",
            tags=(),
        )
    )
    assert 'class="empty-state"' in empty_html

    # Writer tracers write to pre-computed paths.
    written_idx = write_tag_index(
        index, render_html=lambda idx: "<html>tags</html>", output_dir=tmp_path
    )
    assert written_idx == (tmp_path / "tags" / "index.html",)
    assert written_idx[0].exists()

    written_arcs = write_tag_archives(
        (archive,),
        render_html=lambda arc: f"<html>{arc.tag_name}</html>",
        output_dir=tmp_path,
    )
    assert (tmp_path / "tags" / "python" / "index.html").exists()
    assert len(written_arcs) == 1


def test_legacy_html_adapter() -> None:
    """Legacy render_tags_page / render_tag_page adapt to internal models
    with legacy .html hrefs."""
    render = _render_service()

    # Tags index page.
    idx_html = render.render_tags_page(
        tags=["python", "web"], tag_counts={"python": 3, "web": 1}
    )
    assert 'href="/tag/python.html"' in idx_html
    assert "/tags/python/" not in idx_html
    assert "https://example.com/tag/" in idx_html

    # Tag archive page.
    issue = _mock_issue(number=1, title="Tagged Post", labels=["python", "web"])
    tag_html = render.render_tag_page(
        "python", [issue], tags=["python", "web"], issue_slugs={"1": "1-python"}
    )
    assert "/blog/1-python.html" in tag_html
    assert "/blog/1-python/" not in tag_html
    assert 'href="/tag/python.html"' in tag_html
    assert 'href="/tag/web.html"' in tag_html
    assert "https://example.com/tag/python.html" in tag_html
