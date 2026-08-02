"""Tests for the Blog tag taxonomy (Ticket 07)."""

from __future__ import annotations

import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import HttpUrl

from github_blog.config import (
    AboutConfig,
    GithubConfig,
    PathsConfig,
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
        paths=PathsConfig(theme="Escape1"),
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
    return RenderService(
        Settings.model_validate(
            {
                "github": {"repo": "user/repo", "allowed_authors": ["alice"]},
                "site": {
                    "title": "Test Blog",
                    "url": "https://example.com/",
                    "author": "Author",
                    "description": "Test Description",
                    "language": "en",
                },
                "about": {"issue_number": 1},
                "paths": {"theme": theme},
                "profile": {"avatar": "", "bio": "Test bio", "links": []},
                "comments": {
                    "provider": "utterances",
                    "theme": "github-light",
                    "theme_mode": "auto",
                },
                "security": {"token_env": "G_T"},
            }
        )
    )


def test_nfc_casefold_samepost_dedup_count() -> None:
    """NFC + casefold dedup, same-post duplicates counted once, count
    aggregation across posts, deterministic display/order."""
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
            BlogTag(name="risk-management", path="/tags/risk-management/"),
            BlogTag(
                name="RISK-MANAGEMENT", path="/tags/risk-management/"
            ),  # same-post dup
        ),
    )
    result = TagTaxonomyBuilder(_settings()).build([p1, p2, p3])

    # Two unique tags after dedup, sorted alphabetically by key.
    names = [t.name for t in result.index.tags]
    assert names == ["python", "risk-management"]

    # python: p1 + p2 (p2 counted once despite duplicate within post).
    assert result.index.tags[0].count == 2
    # risk-management: p3 only (counted once).
    assert result.index.tags[1].count == 1

    # Display value is the casefold key (deterministic).
    assert result.index.tags[0].name == "python"

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
    assert [e.issue_number for e in archive.entries] == [2, 1]

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
                issue_number=41,
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
