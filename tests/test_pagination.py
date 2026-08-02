"""Production-seam tests for the paginated Blog archive."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from github_blog.blog_archive import BlogArchiveBuilder, write_archive_pages
from github_blog.config import Settings
from github_blog.models.blog_archive import ArchiveEntry, ArchivePage, ArchivePageRoute
from github_blog.models.blog_post import BlogPost, BlogTag
from github_blog.services.render_service import RenderService

PROJECT_ROOT = Path(__file__).parent.parent.absolute()


def _settings(*, theme: str = "Escape1", page_size: int | None = None) -> Settings:
    paths: dict[str, object] = {"theme": theme}
    if page_size is not None:
        paths["page_size"] = page_size
    return Settings.model_validate(
        {
            "github": {"repo": "user/repo", "allowed_authors": ["user"]},
            "site": {
                "title": "Test Blog",
                "url": "https://example.com/",
                "author": "Author",
                "description": "Test Description",
            },
            "about": {"issue_number": 1},
            "paths": paths,
            "security": {"token_env": "TEST_TOKEN"},
        }
    )


def _post(
    issue_number: int,
    published_at: datetime,
    *,
    title: str | None = None,
    slug: str | None = None,
    tags: tuple[BlogTag, ...] = (),
) -> BlogPost:
    slug = slug or f"post-{issue_number}"
    return BlogPost(
        issue_number=issue_number,
        title=title or f"Post {issue_number}",
        slug=slug,
        description="Description",
        created_date=published_at.strftime("%Y-%m-%d"),
        published_at=published_at,
        updated_at=published_at,
        tags=tags,
        body_html="<p>Body.</p>",
        canonical_path=f"/blog/{slug}/",
    )


def _posts(count: int) -> list[BlogPost]:
    return [
        _post(number, datetime(2024, 1, number, tzinfo=timezone.utc))
        for number in range(1, count + 1)
    ]


def _build(posts: list[BlogPost], *, page_size: int = 10) -> tuple[ArchivePage, ...]:
    return BlogArchiveBuilder(_settings(page_size=page_size)).build(posts)


def _render(theme: str = "Escape1") -> RenderService:
    return RenderService(_settings(theme=theme))


def _legacy_issue(
    number: int,
    *,
    title: str | None = None,
    labels: list[str] | None = None,
) -> Any:  # noqa: ANN401
    issue = MagicMock()
    issue.number = number
    issue.title = title or f"Post {number}"
    issue.labels = []
    for label_name in labels or []:
        label = MagicMock()
        label.name = label_name
        issue.labels.append(label)
    issue.created_at = datetime(2024, 1, number, tzinfo=timezone.utc)
    return issue


class TestBlogArchiveBuilder:
    def test_sorts_by_published_at_descending(self) -> None:
        posts = [
            _post(1, datetime(2024, 1, 1, tzinfo=timezone.utc), title="Older"),
            _post(2, datetime(2024, 2, 1, tzinfo=timezone.utc), title="Newer"),
        ]
        pages = _build(posts)
        assert [entry.title for entry in pages[0].entries] == ["Newer", "Older"]

    def test_uses_issue_number_descending_for_timestamp_ties(self) -> None:
        timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
        pages = _build([_post(1, timestamp), _post(3, timestamp), _post(2, timestamp)])
        assert [entry.title for entry in pages[0].entries] == [
            "Post 3",
            "Post 2",
            "Post 1",
        ]

    def test_honors_exact_page_size_boundary(self) -> None:
        pages = _build(_posts(10), page_size=10)
        assert len(pages) == 1
        assert len(pages[0].entries) == 10
        assert pages[0].prev_route is None
        assert pages[0].next_route is None

    def test_honors_page_size_overflow(self) -> None:
        pages = _build(_posts(11), page_size=10)
        assert [len(page.entries) for page in pages] == [10, 1]

    def test_uses_config_default_page_size_ten(self) -> None:
        settings = _settings()
        assert settings.paths.page_size == 10
        pages = BlogArchiveBuilder(settings).build(_posts(11))
        assert [len(page.entries) for page in pages] == [10, 1]

    def test_routes_page_one_page_two_and_last_page(self) -> None:
        pages = _build(_posts(21), page_size=10)
        assert pages[0].route == ArchivePageRoute(
            canonical_path="/blog/", output_path="blog/index.html"
        )
        assert pages[1].route == ArchivePageRoute(
            canonical_path="/blog/page/2/",
            output_path="blog/page/2/index.html",
        )
        assert pages[2].route == ArchivePageRoute(
            canonical_path="/blog/page/3/",
            output_path="blog/page/3/index.html",
        )
        assert pages[2].canonical_url == "https://example.com/blog/page/3/"

    def test_precomputes_prev_and_next_routes(self) -> None:
        pages = _build(_posts(21), page_size=10)
        assert pages[0].prev_route is None
        assert pages[0].next_route == pages[1].route
        assert pages[1].prev_route == pages[0].route
        assert pages[1].next_route == pages[2].route
        assert pages[2].prev_route == pages[1].route
        assert pages[2].next_route is None

    def test_precomputes_detail_and_tag_links(self) -> None:
        tags = (BlogTag(name="python", path="/tags/python/"),)
        pages = _build(
            [
                _post(
                    1,
                    datetime(2024, 1, 1, tzinfo=timezone.utc),
                    slug="stable-slug",
                    tags=tags,
                )
            ]
        )
        entry = pages[0].entries[0]
        assert entry.detail_path == "/blog/stable-slug/"
        assert entry.tags == tags

    def test_empty_input_produces_intentional_page(self) -> None:
        pages = _build([])
        assert len(pages) == 1
        assert pages[0].entries == ()
        assert pages[0].page_number == pages[0].total_pages == 1
        assert pages[0].route.output_path == "blog/index.html"
        assert pages[0].canonical_url == "https://example.com/blog/"
        assert pages[0].prev_route is None
        assert pages[0].next_route is None


class TestArchiveRendering:
    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_theme_renders_only_internal_archive_model(self, theme: str) -> None:
        page = _build(
            [
                _post(
                    1,
                    datetime(2024, 1, 1, tzinfo=timezone.utc),
                    slug="internal-model",
                    tags=(BlogTag(name="python", path="/tags/python/"),),
                )
            ]
        )[0]
        html = _render(theme).render_blog_archive(page)
        assert "Post 1" in html
        assert 'href="/blog/internal-model/"' in html
        assert 'href="/tags/python/"' in html
        assert 'href="https://example.com/blog/"' in html

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_theme_renders_equivalent_pagination(self, theme: str) -> None:
        html = _render(theme).render_blog_archive(_build(_posts(11))[0])
        assert 'href="/blog/page/2/"' in html
        assert "1 / 2" in html
        assert 'class="pagination-prev disabled"' in html

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_theme_renders_empty_page(self, theme: str) -> None:
        html = _render(theme).render_blog_archive(_build([])[0])
        assert 'href="https://example.com/blog/"' in html
        assert 'class="empty-state"' in html
        assert "No blog posts yet." in html
        assert 'class="pagination"' not in html

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_template_does_not_concat_routes_or_access_issues(self, theme: str) -> None:
        template = (PROJECT_ROOT / "templates" / theme / "index.html").read_text(
            encoding="utf-8"
        )
        for forbidden in (
            "/blog/{{",
            "/tag/{{",
            "/blog/page/{{",
            "issue.",
            "issue_slugs",
            "labels",
            "pagination.",
            "blog_url",
        ):
            assert forbidden not in template
        assert "archive_page" in template
        assert "entry.detail_path" in template

    def test_archive_models_do_not_expose_pygithub_objects(self) -> None:
        entry = ArchiveEntry(
            title="Post", created_date="2024-01-01", detail_path="/blog/post/", tags=()
        )
        page = ArchivePage(
            page_number=1,
            total_pages=1,
            route=ArchivePageRoute("/blog/", "blog/index.html"),
            canonical_url="https://example.com/blog/",
            prev_route=None,
            next_route=None,
            entries=(entry,),
        )
        for leaked_name in ("issue", "issues", "issue_slugs", "labels", "pagination"):
            assert not hasattr(entry, leaked_name)
            assert not hasattr(page, leaked_name)


class TestStrictArchiveTracer:
    def test_writes_directory_indexes_from_route_output_paths(
        self, tmp_path: Path
    ) -> None:
        pages = _build(_posts(11))
        written = write_archive_pages(pages, _render().render_blog_archive, tmp_path)
        assert written == (
            tmp_path / "blog/index.html",
            tmp_path / "blog/page/2/index.html",
        )
        assert all(path.exists() for path in written)
        assert not (tmp_path / "blog/page/2.html").exists()

    def test_writes_empty_archive_index(self, tmp_path: Path) -> None:
        pages = _build([])
        write_archive_pages(pages, _render().render_blog_archive, tmp_path)
        output = tmp_path / pages[0].route.output_path
        assert output.exists()
        assert "https://example.com/blog/" in output.read_text(encoding="utf-8")


class TestLegacyArchiveAdapter:
    def test_precomputes_legacy_detail_and_tag_hrefs(self) -> None:
        html = _render().render_index(
            [_legacy_issue(1, title="Legacy", labels=["python"])],
            tags=["python"],
            pagination={
                "page": 1,
                "pages": 1,
                "has_prev": False,
                "has_next": False,
                "prev_num": 0,
                "next_num": 2,
            },
            issue_slugs={"1": "1-legacy"},
        )
        assert 'href="/blog/1-legacy.html"' in html
        assert 'href="/tag/python.html"' in html
        assert "/blog/1-legacy/" not in html
        assert 'href="https://example.com/blog/"' in html

    def test_precomputes_legacy_pagination_and_page_two_canonical(self) -> None:
        html = _render().render_index(
            [_legacy_issue(1)],
            tags=[],
            pagination={
                "page": 2,
                "pages": 3,
                "has_prev": True,
                "has_next": True,
                "prev_num": 1,
                "next_num": 3,
            },
            issue_slugs={"1": "1-legacy"},
        )
        assert 'href="https://example.com/blog/page/2.html"' in html
        assert 'href="/blog/page/1.html"' in html
        assert 'href="/blog/page/3.html"' in html
