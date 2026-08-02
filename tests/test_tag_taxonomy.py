"""Tests for the Blog tag taxonomy (Ticket 07).

Covers:
- TagTaxonomyBuilder: only valid published Blog tags enter, NFC/casefold
  dedup, same-post duplicates, deterministic order/display, post order,
  routes/output/canonical, local collision, empty index/no archives.
- Compiler -> Taxonomy integration: unpublished/Idea/unauthorized excluded.
- RenderService strict seams: render_tag_index / render_tag_archive.
- Template migration: both themes consume internal models only, no
  PyGithub/labels/issue_slugs; forbidden old inputs.
- Legacy CLI regression: render_tags_page / render_tag_page adapt to
  same internal models, legacy .html hrefs self-consistent.
- Strict writer tracers: write_tag_index / write_tag_archives.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import HttpUrl

from github_blog.blog_compiler import BlogCompiler
from github_blog.config import (
    AboutConfig,
    GithubConfig,
    SecurityConfig,
    Settings,
    SiteConfig,
)
from github_blog.models.blog_post import BlogPost, BlogTag
from github_blog.models.issue_snapshot import IssueSnapshot
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent.absolute()

_DEFAULT_PUBLISHED = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)
_DEFAULT_UPDATED = datetime(2026, 1, 11, 8, 30, tzinfo=timezone.utc)


def _make_settings() -> Settings:
    return Settings(
        github=GithubConfig(
            repo="user/repo",
            allowed_authors=["alice"],
        ),
        site=SiteConfig(
            title="Test Blog",
            url=HttpUrl("https://example.com/"),
            author="Test",
        ),
        about=AboutConfig(issue_number=1),
        security=SecurityConfig(token_env="G_T"),  # noqa: S106
    )


def _make_blog_tag(name: str, path: str | None = None) -> BlogTag:
    if path is None:
        key = unicodedata.normalize("NFC", name).casefold()
        path = f"/tags/{key}/"
    return BlogTag(name=name, path=path)


def _make_blog_post(
    issue_number: int = 1,
    title: str = "Test Post",
    slug: str = "test-post",
    tags: tuple[BlogTag, ...] = (),
    published_at: datetime = _DEFAULT_PUBLISHED,
    created_date: str = "2026-01-05",
) -> BlogPost:
    return BlogPost(
        issue_number=issue_number,
        title=title,
        slug=slug,
        description="A test post.",
        created_date=created_date,
        published_at=published_at,
        updated_at=_DEFAULT_UPDATED,
        tags=tags,
        body_html="<p>Body.</p>",
        canonical_path=f"/blog/{slug}/",
    )


def _make_render_service(theme: str = "Escape1") -> RenderService:
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


def _make_mock_issue(
    number: int = 1,
    title: str = "Test Post",
    body: str = "body",
    labels: list[str] | None = None,
) -> Any:  # noqa: ANN401
    issue = MagicMock()
    issue.number = number
    issue.title = title
    issue.body = body
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


# ===========================================================================
# TagTaxonomyBuilder: aggregation and normalization
# ===========================================================================


class TestTagAggregation:
    """Tags are aggregated from BlogPost.tags only."""

    def test_single_post_single_tag(self) -> None:
        post = _make_blog_post(tags=(_make_blog_tag("python"),))
        result = TagTaxonomyBuilder(_make_settings()).build([post])
        assert len(result.index.tags) == 1
        assert result.index.tags[0].name == "python"
        assert result.index.tags[0].count == 1

    def test_multiple_posts_same_tag_counted(self) -> None:
        p1 = _make_blog_post(issue_number=1, tags=(_make_blog_tag("python"),))
        p2 = _make_blog_post(issue_number=2, slug="b", tags=(_make_blog_tag("python"),))
        result = TagTaxonomyBuilder(_make_settings()).build([p1, p2])
        assert len(result.index.tags) == 1
        assert result.index.tags[0].count == 2

    def test_different_tags_separate(self) -> None:
        p1 = _make_blog_post(issue_number=1, tags=(_make_blog_tag("python"),))
        p2 = _make_blog_post(issue_number=2, slug="b", tags=(_make_blog_tag("rust"),))
        result = TagTaxonomyBuilder(_make_settings()).build([p1, p2])
        assert len(result.index.tags) == 2

    def test_post_with_multiple_tags(self) -> None:
        post = _make_blog_post(
            tags=(_make_blog_tag("python"), _make_blog_tag("web")),
        )
        result = TagTaxonomyBuilder(_make_settings()).build([post])
        assert len(result.index.tags) == 2


class TestNfcCasefoldDedup:
    """NFC + casefold comparison and deduplication."""

    def test_casefold_duplicates_merged(self) -> None:
        """Tags differing only in case are merged into one."""
        p1 = _make_blog_post(
            issue_number=1,
            tags=(BlogTag(name="Python", path="/tags/python/"),),
        )
        p2 = _make_blog_post(
            issue_number=2,
            slug="b",
            tags=(BlogTag(name="python", path="/tags/python/"),),
        )
        result = TagTaxonomyBuilder(_make_settings()).build([p1, p2])
        assert len(result.index.tags) == 1
        assert result.index.tags[0].count == 2

    def test_nfc_duplicates_merged(self) -> None:
        """Tags that are NFC-equivalent are merged."""
        # "café" in composed (NFC) vs decomposed (NFD) form
        composed = "café"
        decomposed = "cafe\u0301"
        p1 = _make_blog_post(
            issue_number=1,
            tags=(BlogTag(name=composed, path="/tags/café/"),),
        )
        p2 = _make_blog_post(
            issue_number=2,
            slug="b",
            tags=(BlogTag(name=decomposed, path="/tags/café/"),),
        )
        result = TagTaxonomyBuilder(_make_settings()).build([p1, p2])
        assert len(result.index.tags) == 1
        assert result.index.tags[0].count == 2

    def test_across_post_and_within_post_dedup(self) -> None:
        """Same tag in different posts and duplicated within a post."""
        p1 = _make_blog_post(
            issue_number=1,
            tags=(
                BlogTag(name="python", path="/tags/python/"),
                BlogTag(name="Python", path="/tags/python/"),
            ),
        )
        p2 = _make_blog_post(
            issue_number=2,
            slug="b",
            tags=(BlogTag(name="python", path="/tags/python/"),),
        )
        result = TagTaxonomyBuilder(_make_settings()).build([p1, p2])
        assert len(result.index.tags) == 1
        # p1 contributes once (dedup within post), p2 contributes once
        assert result.index.tags[0].count == 2


class TestSamePostDuplicate:
    """Same-post duplicate tags are not counted twice."""

    def test_same_tag_twice_in_one_post_counts_once(self) -> None:
        post = _make_blog_post(
            tags=(
                BlogTag(name="python", path="/tags/python/"),
                BlogTag(name="python", path="/tags/python/"),
            ),
        )
        result = TagTaxonomyBuilder(_make_settings()).build([post])
        assert len(result.index.tags) == 1
        assert result.index.tags[0].count == 1

    def test_same_tag_casefold_twice_in_one_post_counts_once(self) -> None:
        post = _make_blog_post(
            tags=(
                BlogTag(name="Python", path="/tags/python/"),
                BlogTag(name="PYTHON", path="/tags/python/"),
            ),
        )
        result = TagTaxonomyBuilder(_make_settings()).build([post])
        assert len(result.index.tags) == 1
        assert result.index.tags[0].count == 1

    def test_archive_has_post_once(self) -> None:
        """A post with duplicate tags appears only once in the tag archive."""
        post = _make_blog_post(
            issue_number=42,
            title="Dup Tag Post",
            tags=(
                BlogTag(name="python", path="/tags/python/"),
                BlogTag(name="python", path="/tags/python/"),
            ),
        )
        result = TagTaxonomyBuilder(_make_settings()).build([post])
        archive = result.archives[0]
        assert len(archive.entries) == 1
        assert archive.entries[0].title == "Dup Tag Post"


# ===========================================================================
# TagTaxonomyBuilder: deterministic order and display
# ===========================================================================


class TestDeterministicOrder:
    """Tag ordering and display values are deterministic."""

    def test_tags_sorted_alphabetically_by_key(self) -> None:
        p1 = _make_blog_post(issue_number=1, tags=(_make_blog_tag("zebra"),))
        p2 = _make_blog_post(issue_number=2, slug="b", tags=(_make_blog_tag("apple"),))
        p3 = _make_blog_post(issue_number=3, slug="c", tags=(_make_blog_tag("mango"),))
        result = TagTaxonomyBuilder(_make_settings()).build([p1, p2, p3])
        names = [t.name for t in result.index.tags]
        assert names == ["apple", "mango", "zebra"]

    def test_order_independent_of_post_order(self) -> None:
        """Same posts in different input order produce same tag order."""
        p1 = _make_blog_post(issue_number=1, tags=(_make_blog_tag("zebra"),))
        p2 = _make_blog_post(issue_number=2, slug="b", tags=(_make_blog_tag("apple"),))
        r1 = TagTaxonomyBuilder(_make_settings()).build([p1, p2])
        r2 = TagTaxonomyBuilder(_make_settings()).build([p2, p1])
        assert [t.name for t in r1.index.tags] == [t.name for t in r2.index.tags]

    def test_display_value_is_deterministic(self) -> None:
        """Merged duplicates have a deterministic display value."""
        p1 = _make_blog_post(
            issue_number=1,
            tags=(BlogTag(name="Python", path="/tags/python/"),),
        )
        p2 = _make_blog_post(
            issue_number=2,
            slug="b",
            tags=(BlogTag(name="PYTHON", path="/tags/python/"),),
        )
        result = TagTaxonomyBuilder(_make_settings()).build([p1, p2])
        assert len(result.index.tags) == 1
        # Display value is the NFC+casefold key (deterministic)
        assert result.index.tags[0].name == "python"


# ===========================================================================
# TagTaxonomyBuilder: post order in archives
# ===========================================================================


class TestArchivePostOrder:
    """Tag archives are sorted by accepted Blog publication order."""

    def test_archive_sorted_by_publication_desc(self) -> None:
        p_old = _make_blog_post(
            issue_number=1,
            slug="old",
            title="Old Post",
            tags=(_make_blog_tag("python"),),
            published_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        p_new = _make_blog_post(
            issue_number=2,
            slug="new",
            title="New Post",
            tags=(_make_blog_tag("python"),),
            published_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        result = TagTaxonomyBuilder(_make_settings()).build([p_old, p_new])
        archive = result.archives[0]
        assert archive.entries[0].title == "New Post"
        assert archive.entries[1].title == "Old Post"

    def test_archive_tiebreaker_issue_number_desc(self) -> None:
        """Same published_at sorts by issue_number descending."""
        t = datetime(2026, 1, 1, tzinfo=timezone.utc)
        p1 = _make_blog_post(
            issue_number=1,
            slug="a",
            title="Post 1",
            tags=(_make_blog_tag("python"),),
            published_at=t,
        )
        p2 = _make_blog_post(
            issue_number=3,
            slug="c",
            title="Post 3",
            tags=(_make_blog_tag("python"),),
            published_at=t,
        )
        p3 = _make_blog_post(
            issue_number=2,
            slug="b",
            title="Post 2",
            tags=(_make_blog_tag("python"),),
            published_at=t,
        )
        result = TagTaxonomyBuilder(_make_settings()).build([p1, p2, p3])
        archive = result.archives[0]
        titles = [e.title for e in archive.entries]
        assert titles == ["Post 3", "Post 2", "Post 1"]


# ===========================================================================
# TagTaxonomyBuilder: routes, output, canonical
# ===========================================================================


class TestRoutesAndCanonical:
    """Routes, output paths, and canonical URLs are pre-computed."""

    def test_tags_index_route(self) -> None:
        post = _make_blog_post(tags=(_make_blog_tag("python"),))
        result = TagTaxonomyBuilder(_make_settings()).build([post])
        assert result.index.route.canonical_path == "/tags/"
        assert result.index.route.output_path == "tags/index.html"

    def test_tags_index_canonical_url(self) -> None:
        post = _make_blog_post(tags=(_make_blog_tag("python"),))
        result = TagTaxonomyBuilder(_make_settings()).build([post])
        assert result.index.canonical_url == "https://example.com/tags/"

    def test_tag_archive_route(self) -> None:
        post = _make_blog_post(tags=(_make_blog_tag("python"),))
        result = TagTaxonomyBuilder(_make_settings()).build([post])
        archive = result.archives[0]
        assert archive.route.canonical_path == "/tags/python/"
        assert archive.route.output_path == "tags/python/index.html"

    def test_tag_archive_canonical_url(self) -> None:
        post = _make_blog_post(tags=(_make_blog_tag("python"),))
        result = TagTaxonomyBuilder(_make_settings()).build([post])
        archive = result.archives[0]
        assert archive.canonical_url == "https://example.com/tags/python/"

    def test_tag_summary_route_points_to_archive(self) -> None:
        post = _make_blog_post(tags=(_make_blog_tag("python"),))
        result = TagTaxonomyBuilder(_make_settings()).build([post])
        summary = result.index.tags[0]
        assert summary.route.canonical_path == "/tags/python/"
        assert summary.route.output_path == "tags/python/index.html"

    def test_entry_detail_link_uses_blog_canonical(self) -> None:
        """Entry detail_path is the BlogPost canonical_path."""
        post = _make_blog_post(
            slug="my-slug",
            tags=(_make_blog_tag("python"),),
        )
        result = TagTaxonomyBuilder(_make_settings()).build([post])
        archive = result.archives[0]
        assert archive.entries[0].detail_path == "/blog/my-slug/"

    def test_entry_carries_post_tags(self) -> None:
        post = _make_blog_post(
            tags=(_make_blog_tag("python"), _make_blog_tag("web")),
        )
        result = TagTaxonomyBuilder(_make_settings()).build([post])
        archive = result.archives[0]
        entry = archive.entries[0]
        assert len(entry.tags) == 2
        tag_names = {t.name for t in entry.tags}
        assert tag_names == {"python", "web"}

    def test_archive_index_route_points_to_tags_index(self) -> None:
        post = _make_blog_post(tags=(_make_blog_tag("python"),))
        result = TagTaxonomyBuilder(_make_settings()).build([post])
        archive = result.archives[0]
        assert archive.index_route.canonical_path == "/tags/"
        assert archive.index_route.output_path == "tags/index.html"


# ===========================================================================
# TagTaxonomyBuilder: local route collision
# ===========================================================================


class TestLocalRouteCollision:
    """Local route registration and collision detection."""

    def test_no_collision_with_normal_tags(self) -> None:
        post = _make_blog_post(
            tags=(_make_blog_tag("python"), _make_blog_tag("rust")),
        )
        result = TagTaxonomyBuilder(_make_settings()).build([post])
        assert not result.has_errors
        assert len(result.archives) == 2

    def test_collision_detected_for_casefold_duplicates(self) -> None:
        """Two tags that casefold to the same key must not produce a collision
        error because the builder already deduplicates them."""
        post = _make_blog_post(
            tags=(
                BlogTag(name="python", path="/tags/python/"),
                BlogTag(name="Python", path="/tags/python/"),
            ),
        )
        result = TagTaxonomyBuilder(_make_settings()).build([post])
        # Dedup means only one route is registered; no collision.
        assert not result.has_errors
        assert len(result.archives) == 1

    def test_collision_safety_net_detects_duplicate_routes(self) -> None:
        """The local collision check detects duplicate canonical paths.

        This is a white-box test of the safety net: under normal operation
        the builder deduplicates tags by key, so two tags cannot produce
        the same route.  This test verifies that the check itself works
        by feeding it crafted duplicate aggregated tags.
        """
        from github_blog.tag_taxonomy import _AggregatedTag

        builder = TagTaxonomyBuilder(_make_settings())
        aggregated = (
            _AggregatedTag(key="python", display_name="python", posts=()),
            _AggregatedTag(key="python", display_name="python", posts=()),
        )
        diagnostics = builder._check_collisions(aggregated)
        assert any(d.code == "TAG_ROUTE_COLLISION" for d in diagnostics)

    def test_collision_blocks_archives_but_keeps_index(self) -> None:
        """When a collision is detected, archives are empty but index remains."""
        from github_blog.tag_taxonomy import _AggregatedTag

        class _CollisionBuilder(TagTaxonomyBuilder):
            """Builder that returns duplicate-key tags to trigger collision."""

            def _aggregate(
                self, posts: Sequence[BlogPost]
            ) -> tuple[_AggregatedTag, ...]:
                return (
                    _AggregatedTag(key="python", display_name="python", posts=()),
                    _AggregatedTag(key="python", display_name="python", posts=()),
                )

        builder = _CollisionBuilder(_make_settings())
        result = builder.build([])
        assert result.has_errors
        assert result.archives == ()
        # Index is still present for empty-state rendering.
        assert result.index is not None
        assert result.index.route.canonical_path == "/tags/"


# ===========================================================================
# TagTaxonomyBuilder: empty state
# ===========================================================================


class TestEmptyState:
    """Empty tags produce an intentional index and no spurious archives."""

    def test_empty_posts_produce_index(self) -> None:
        result = TagTaxonomyBuilder(_make_settings()).build([])
        assert result.index is not None
        assert result.index.route.canonical_path == "/tags/"
        assert result.index.route.output_path == "tags/index.html"
        assert result.index.tags == ()

    def test_empty_posts_produce_no_archives(self) -> None:
        result = TagTaxonomyBuilder(_make_settings()).build([])
        assert result.archives == ()

    def test_posts_without_tags_produce_index(self) -> None:
        post = _make_blog_post(tags=())
        result = TagTaxonomyBuilder(_make_settings()).build([post])
        assert result.index is not None
        assert result.index.tags == ()

    def test_posts_without_tags_produce_no_archives(self) -> None:
        post = _make_blog_post(tags=())
        result = TagTaxonomyBuilder(_make_settings()).build([post])
        assert result.archives == ()

    def test_empty_index_has_canonical(self) -> None:
        result = TagTaxonomyBuilder(_make_settings()).build([])
        assert result.index.canonical_url == "https://example.com/tags/"


# ===========================================================================
# Compiler -> Taxonomy integration: only valid published Blog tags enter
# ===========================================================================


_VALID_BLOG_BODY = (
    "---\n"
    "slug: my-post\n"
    "description: A post.\n"
    'created_date: "2026-01-05"\n'
    "---\n\n"
    "Body.\n"
)


def _make_snapshot(
    number: int = 1,
    *,
    title: str = "Test Post",
    body: str = _VALID_BLOG_BODY,
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


class TestCompilerToTaxonomy:
    """Only valid published Blog tags enter the taxonomy."""

    def test_published_blog_tags_enter(self) -> None:
        snap = _make_snapshot(
            labels=("type:blog", "published", "tag:python", "tag:web"),
        )
        result = BlogCompiler(_make_settings()).compile([snap])
        assert len(result.posts) == 1
        taxonomy = TagTaxonomyBuilder(_make_settings()).build(result.posts)
        names = {t.name for t in taxonomy.index.tags}
        assert names == {"python", "web"}

    def test_unpublished_tags_do_not_enter(self) -> None:
        snap = _make_snapshot(
            labels=("type:blog", "tag:python"),
            body="no front matter, no published",
        )
        result = BlogCompiler(_make_settings()).compile([snap])
        assert result.posts == ()
        taxonomy = TagTaxonomyBuilder(_make_settings()).build(result.posts)
        assert taxonomy.index.tags == ()
        assert taxonomy.archives == ()

    def test_idea_tags_do_not_enter(self) -> None:
        snap = _make_snapshot(labels=("type:idea", "published", "tag:python"))
        result = BlogCompiler(_make_settings()).compile([snap])
        assert result.posts == ()
        taxonomy = TagTaxonomyBuilder(_make_settings()).build(result.posts)
        assert taxonomy.index.tags == ()

    def test_unauthorized_author_tags_do_not_enter(self) -> None:
        snap = _make_snapshot(
            author="bob", labels=("type:blog", "published", "tag:python")
        )
        result = BlogCompiler(_make_settings()).compile([snap])
        assert result.posts == ()
        taxonomy = TagTaxonomyBuilder(_make_settings()).build(result.posts)
        assert taxonomy.index.tags == ()

    def test_pr_tags_do_not_enter(self) -> None:
        snap = _make_snapshot(
            is_pull_request=True,
            labels=("type:blog", "published", "tag:python"),
        )
        result = BlogCompiler(_make_settings()).compile([snap])
        assert result.posts == ()
        taxonomy = TagTaxonomyBuilder(_make_settings()).build(result.posts)
        assert taxonomy.index.tags == ()


# ===========================================================================
# RenderService strict seams
# ===========================================================================


class TestRenderTagIndex:
    """render_tag_index renders from the internal TagsIndex model."""

    def test_renders_tag_name(self) -> None:
        render = _make_render_service()
        index = TagsIndex(
            route=TagsIndexRoute(
                canonical_path="/tags/", output_path="tags/index.html"
            ),
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
        html = render.render_tag_index(index)
        assert "python" in html
        assert "3" in html

    def test_renders_canonical_url(self) -> None:
        render = _make_render_service()
        index = TagsIndex(
            route=TagsIndexRoute(
                canonical_path="/tags/", output_path="tags/index.html"
            ),
            canonical_url="https://example.com/tags/",
            tags=(),
        )
        html = render.render_tag_index(index)
        assert "https://example.com/tags/" in html

    def test_renders_tag_archive_link(self) -> None:
        render = _make_render_service()
        index = TagsIndex(
            route=TagsIndexRoute(
                canonical_path="/tags/", output_path="tags/index.html"
            ),
            canonical_url="https://example.com/tags/",
            tags=(
                TagSummary(
                    name="python",
                    count=1,
                    route=TagArchiveRoute(
                        canonical_path="/tags/python/",
                        output_path="tags/python/index.html",
                    ),
                ),
            ),
        )
        html = render.render_tag_index(index)
        assert 'href="/tags/python/"' in html

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_empty_index_renders_intentional_state(self, theme: str) -> None:
        render = _make_render_service(theme)
        index = TagsIndex(
            route=TagsIndexRoute(
                canonical_path="/tags/", output_path="tags/index.html"
            ),
            canonical_url="https://example.com/tags/",
            tags=(),
        )
        html = render.render_tag_index(index)
        assert 'class="empty-state"' in html
        assert "No blog tags yet." in html


class TestRenderTagArchive:
    """render_tag_archive renders from the internal TagArchive model."""

    def test_renders_tag_name(self) -> None:
        render = _make_render_service()
        archive = TagArchive(
            route=TagArchiveRoute(
                canonical_path="/tags/python/",
                output_path="tags/python/index.html",
            ),
            canonical_url="https://example.com/tags/python/",
            tag_name="python",
            index_route=TagsIndexRoute(
                canonical_path="/tags/",
                output_path="tags/index.html",
            ),
            entries=(
                TagArchiveEntry(
                    title="My Post",
                    created_date="2026-01-05",
                    detail_path="/blog/my-post/",
                    tags=(_make_blog_tag("python"),),
                ),
            ),
        )
        html = render.render_tag_archive(archive)
        assert "python" in html.lower()

    def test_renders_canonical_url(self) -> None:
        render = _make_render_service()
        archive = TagArchive(
            route=TagArchiveRoute(
                canonical_path="/tags/python/",
                output_path="tags/python/index.html",
            ),
            canonical_url="https://example.com/tags/python/",
            tag_name="python",
            index_route=TagsIndexRoute(
                canonical_path="/tags/",
                output_path="tags/index.html",
            ),
            entries=(),
        )
        html = render.render_tag_archive(archive)
        assert "https://example.com/tags/python/" in html

    def test_renders_entry_detail_link(self) -> None:
        render = _make_render_service()
        archive = TagArchive(
            route=TagArchiveRoute(
                canonical_path="/tags/python/",
                output_path="tags/python/index.html",
            ),
            canonical_url="https://example.com/tags/python/",
            tag_name="python",
            index_route=TagsIndexRoute(
                canonical_path="/tags/",
                output_path="tags/index.html",
            ),
            entries=(
                TagArchiveEntry(
                    title="My Post",
                    created_date="2026-01-05",
                    detail_path="/blog/my-post/",
                    tags=(),
                ),
            ),
        )
        html = render.render_tag_archive(archive)
        assert 'href="/blog/my-post/"' in html

    def test_no_html_url_construction(self) -> None:
        """Strict archive must not produce .html detail links."""
        render = _make_render_service()
        archive = TagArchive(
            route=TagArchiveRoute(
                canonical_path="/tags/python/",
                output_path="tags/python/index.html",
            ),
            canonical_url="https://example.com/tags/python/",
            tag_name="python",
            index_route=TagsIndexRoute(
                canonical_path="/tags/",
                output_path="tags/index.html",
            ),
            entries=(
                TagArchiveEntry(
                    title="My Post",
                    created_date="2026-01-05",
                    detail_path="/blog/my-post/",
                    tags=(),
                ),
            ),
        )
        html = render.render_tag_archive(archive)
        assert "/blog/my-post.html" not in html
        assert "/blog/my-post/" in html


# ===========================================================================
# Template migration: both themes consume internal models only
# ===========================================================================


class TestTemplateMigrationEscape1:
    """Escape1 templates consume internal models, not PyGithub/labels/slugs."""

    def test_tags_html_no_old_variables(self) -> None:
        """tags.html must render from tags_index model only."""
        render = _make_render_service("Escape1")
        index = TagsIndex(
            route=TagsIndexRoute(
                canonical_path="/tags/", output_path="tags/index.html"
            ),
            canonical_url="https://example.com/tags/",
            tags=(
                TagSummary(
                    name="python",
                    count=2,
                    route=TagArchiveRoute(
                        canonical_path="/tags/python/",
                        output_path="tags/python/index.html",
                    ),
                ),
            ),
        )
        html = render.render_tag_index(index)
        assert "python" in html
        assert 'href="/tags/python/"' in html
        assert "https://example.com/tags/" in html

    def test_tag_html_no_old_variables(self) -> None:
        """tag.html must render from tag_archive model only."""
        render = _make_render_service("Escape1")
        archive = TagArchive(
            route=TagArchiveRoute(
                canonical_path="/tags/python/",
                output_path="tags/python/index.html",
            ),
            canonical_url="https://example.com/tags/python/",
            tag_name="python",
            index_route=TagsIndexRoute(
                canonical_path="/tags/",
                output_path="tags/index.html",
            ),
            entries=(
                TagArchiveEntry(
                    title="Post One",
                    created_date="2026-01-05",
                    detail_path="/blog/post-one/",
                    tags=(_make_blog_tag("python"),),
                ),
            ),
        )
        html = render.render_tag_archive(archive)
        assert "Post One" in html
        assert 'href="/blog/post-one/"' in html
        assert "https://example.com/tags/python/" in html

    def test_tags_html_forbidden_old_inputs_not_used(self) -> None:
        """tags.html must not reference tag_items, tags (as raw list)."""
        render = _make_render_service("Escape1")
        index = TagsIndex(
            route=TagsIndexRoute(
                canonical_path="/tags/", output_path="tags/index.html"
            ),
            canonical_url="https://example.com/tags/",
            tags=(
                TagSummary(
                    name="python",
                    count=1,
                    route=TagArchiveRoute(
                        canonical_path="/tags/python/",
                        output_path="tags/python/index.html",
                    ),
                ),
            ),
        )
        html = render.render_tag_index(index)
        # The old template constructed URLs like /tag/{{ name }}.html.
        # The new template must use the pre-computed route.
        assert "/tag/python.html" not in html
        assert "/tags/python/" in html

    def test_tag_html_forbidden_old_inputs_not_used(self) -> None:
        """tag.html must not reference issues, issue_slugs, labels."""
        render = _make_render_service("Escape1")
        archive = TagArchive(
            route=TagArchiveRoute(
                canonical_path="/tags/python/",
                output_path="tags/python/index.html",
            ),
            canonical_url="https://example.com/tags/python/",
            tag_name="python",
            index_route=TagsIndexRoute(
                canonical_path="/tags/",
                output_path="tags/index.html",
            ),
            entries=(
                TagArchiveEntry(
                    title="My Post",
                    created_date="2026-01-05",
                    detail_path="/blog/my-post/",
                    tags=(_make_blog_tag("python"), _make_blog_tag("web")),
                ),
            ),
        )
        html = render.render_tag_archive(archive)
        # The old template used issue_slugs and labels to construct URLs.
        # The new template must use pre-computed paths.
        assert "/blog/my-post.html" not in html
        assert "/blog/my-post/" in html


class TestTemplateMigrationEscape2:
    """Escape2 templates consume internal models, not PyGithub/labels/slugs."""

    def test_tags_html_no_old_variables(self) -> None:
        render = _make_render_service("Escape2")
        index = TagsIndex(
            route=TagsIndexRoute(
                canonical_path="/tags/", output_path="tags/index.html"
            ),
            canonical_url="https://example.com/tags/",
            tags=(
                TagSummary(
                    name="python",
                    count=2,
                    route=TagArchiveRoute(
                        canonical_path="/tags/python/",
                        output_path="tags/python/index.html",
                    ),
                ),
            ),
        )
        html = render.render_tag_index(index)
        assert "python" in html
        assert 'href="/tags/python/"' in html
        assert "https://example.com/tags/" in html

    def test_tag_html_no_old_variables(self) -> None:
        render = _make_render_service("Escape2")
        archive = TagArchive(
            route=TagArchiveRoute(
                canonical_path="/tags/python/",
                output_path="tags/python/index.html",
            ),
            canonical_url="https://example.com/tags/python/",
            tag_name="python",
            index_route=TagsIndexRoute(
                canonical_path="/tags/",
                output_path="tags/index.html",
            ),
            entries=(
                TagArchiveEntry(
                    title="Post One",
                    created_date="2026-01-05",
                    detail_path="/blog/post-one/",
                    tags=(_make_blog_tag("python"),),
                ),
            ),
        )
        html = render.render_tag_archive(archive)
        assert "Post One" in html
        assert 'href="/blog/post-one/"' in html
        assert "https://example.com/tags/python/" in html


class TestThemeEquivalence:
    """Escape1 and Escape2 render equivalent Tags pages from the same model."""

    def test_tags_index_equivalent_content(self) -> None:
        index = TagsIndex(
            route=TagsIndexRoute(
                canonical_path="/tags/", output_path="tags/index.html"
            ),
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
                TagSummary(
                    name="rust",
                    count=1,
                    route=TagArchiveRoute(
                        canonical_path="/tags/rust/",
                        output_path="tags/rust/index.html",
                    ),
                ),
            ),
        )
        html1 = _make_render_service("Escape1").render_tag_index(index)
        html2 = _make_render_service("Escape2").render_tag_index(index)
        # Both must contain the same tag names, counts, and links
        for needle in ("python", "rust", "/tags/python/", "/tags/rust/"):
            assert needle in html1
            assert needle in html2

    def test_tag_archive_equivalent_content(self) -> None:
        archive = TagArchive(
            route=TagArchiveRoute(
                canonical_path="/tags/python/",
                output_path="tags/python/index.html",
            ),
            canonical_url="https://example.com/tags/python/",
            tag_name="python",
            index_route=TagsIndexRoute(
                canonical_path="/tags/",
                output_path="tags/index.html",
            ),
            entries=(
                TagArchiveEntry(
                    title="My Post",
                    created_date="2026-01-05",
                    detail_path="/blog/my-post/",
                    tags=(_make_blog_tag("python"),),
                ),
            ),
        )
        html1 = _make_render_service("Escape1").render_tag_archive(archive)
        html2 = _make_render_service("Escape2").render_tag_archive(archive)
        for needle in ("My Post", "/blog/my-post/", "python"):
            assert needle in html1
            assert needle in html2


# ===========================================================================
# Legacy CLI regression: render_tags_page / render_tag_page
# ===========================================================================


class TestLegacyRenderTagsPage:
    """Legacy render_tags_page adapts to internal model with legacy paths."""

    def test_renders_tag_name_and_count(self) -> None:
        render = _make_render_service()
        html = render.render_tags_page(
            tags=["python", "web"],
            tag_counts={"python": 3, "web": 1},
        )
        assert "python" in html
        assert "web" in html
        assert "3" in html

    def test_legacy_tag_href_uses_dot_html(self) -> None:
        render = _make_render_service()
        html = render.render_tags_page(
            tags=["python"],
            tag_counts={"python": 1},
        )
        assert 'href="/tag/python.html"' in html
        assert "/tags/python/" not in html

    def test_legacy_canonical_uses_tag_dir(self) -> None:
        render = _make_render_service()
        html = render.render_tags_page(tags=["python"], tag_counts={"python": 1})
        assert "https://example.com/tag/" in html

    def test_empty_tags_renders(self) -> None:
        render = _make_render_service()
        html = render.render_tags_page(tags=[], tag_counts={})
        assert isinstance(html, str)
        assert len(html) > 0


class TestLegacyRenderTagPage:
    """Legacy render_tag_page adapts to internal model with legacy paths."""

    def test_renders_tag_name(self) -> None:
        render = _make_render_service()
        issue = _make_mock_issue(number=1, title="Tagged Post", labels=["python"])
        html = render.render_tag_page(
            "python", [issue], tags=["python"], issue_slugs={"1": "1-python"}
        )
        assert "python" in html.lower()

    def test_legacy_detail_href_uses_dot_html(self) -> None:
        render = _make_render_service()
        issue = _make_mock_issue(number=1, title="Post", labels=["python"])
        html = render.render_tag_page(
            "python", [issue], tags=["python"], issue_slugs={"1": "1-python"}
        )
        assert "/blog/1-python.html" in html
        assert "/blog/1-python/" not in html

    def test_legacy_tag_href_uses_dot_html(self) -> None:
        render = _make_render_service()
        issue = _make_mock_issue(number=1, title="Post", labels=["python", "web"])
        html = render.render_tag_page(
            "python", [issue], tags=["python", "web"], issue_slugs={"1": "1-python"}
        )
        assert 'href="/tag/python.html"' in html
        assert 'href="/tag/web.html"' in html

    def test_legacy_canonical_uses_dot_html(self) -> None:
        render = _make_render_service()
        issue = _make_mock_issue(number=1, title="Post", labels=["python"])
        html = render.render_tag_page(
            "python", [issue], tags=["python"], issue_slugs={"1": "1-python"}
        )
        assert "https://example.com/tag/python.html" in html


# ===========================================================================
# Strict writer tracers
# ===========================================================================


class TestWriteTagIndex:
    """write_tag_index writes to the pre-computed output path."""

    def test_writes_to_tags_index_html(self, tmp_path: Path) -> None:
        index = TagsIndex(
            route=TagsIndexRoute(
                canonical_path="/tags/", output_path="tags/index.html"
            ),
            canonical_url="https://example.com/tags/",
            tags=(),
        )
        written = write_tag_index(
            index,
            render_html=lambda idx: "<html>tags</html>",
            output_dir=tmp_path,
        )
        assert len(written) == 1
        assert written[0] == tmp_path / "tags" / "index.html"
        assert written[0].read_text(encoding="utf-8") == "<html>tags</html>"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        index = TagsIndex(
            route=TagsIndexRoute(
                canonical_path="/tags/", output_path="tags/index.html"
            ),
            canonical_url="https://example.com/tags/",
            tags=(),
        )
        written = write_tag_index(
            index,
            render_html=lambda idx: "content",
            output_dir=tmp_path,
        )
        assert written[0].parent.exists()


class TestWriteTagArchives:
    """write_tag_archives writes each archive to its pre-computed output path."""

    def test_writes_all_archives(self, tmp_path: Path) -> None:
        archives = (
            TagArchive(
                route=TagArchiveRoute(
                    canonical_path="/tags/python/",
                    output_path="tags/python/index.html",
                ),
                canonical_url="https://example.com/tags/python/",
                tag_name="python",
                index_route=TagsIndexRoute(
                    canonical_path="/tags/",
                    output_path="tags/index.html",
                ),
                entries=(),
            ),
            TagArchive(
                route=TagArchiveRoute(
                    canonical_path="/tags/rust/",
                    output_path="tags/rust/index.html",
                ),
                canonical_url="https://example.com/tags/rust/",
                tag_name="rust",
                index_route=TagsIndexRoute(
                    canonical_path="/tags/",
                    output_path="tags/index.html",
                ),
                entries=(),
            ),
        )
        written = write_tag_archives(
            archives,
            render_html=lambda arc: f"<html>{arc.tag_name}</html>",
            output_dir=tmp_path,
        )
        assert len(written) == 2
        assert (tmp_path / "tags" / "python" / "index.html").exists()
        assert (tmp_path / "tags" / "rust" / "index.html").exists()
        assert (tmp_path / "tags" / "python" / "index.html").read_text(
            encoding="utf-8"
        ) == "<html>python</html>"

    def test_empty_archives_writes_nothing(self, tmp_path: Path) -> None:
        written = write_tag_archives(
            (),
            render_html=lambda arc: "content",
            output_dir=tmp_path,
        )
        assert written == ()

    def test_creates_nested_directories(self, tmp_path: Path) -> None:
        archive = TagArchive(
            route=TagArchiveRoute(
                canonical_path="/tags/python/",
                output_path="tags/python/index.html",
            ),
            canonical_url="https://example.com/tags/python/",
            tag_name="python",
            index_route=TagsIndexRoute(
                canonical_path="/tags/",
                output_path="tags/index.html",
            ),
            entries=(),
        )
        write_tag_archives(
            (archive,),
            render_html=lambda arc: "content",
            output_dir=tmp_path,
        )
        assert (tmp_path / "tags" / "python" / "index.html").exists()
