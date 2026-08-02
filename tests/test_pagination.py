"""Production-seam tests for the paginated Blog archive."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from github_blog.blog_archive import BlogArchiveBuilder, write_archive_pages
from github_blog.config import Settings
from github_blog.models.blog_archive import ArchivePageRoute
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


def _render(theme: str = "Escape1") -> RenderService:
    return RenderService(_settings(theme=theme))


class TestBlogArchiveBuilder:
    def test_order_tie_slices_routes_prev_next(self) -> None:
        """One builder scenario: order, tie-break, pagination slices,
        routes, and prev/next linkage."""
        old = datetime(2023, 1, 1, tzinfo=timezone.utc)
        tie = datetime(2024, 6, 1, tzinfo=timezone.utc)
        new = datetime(2024, 7, 1, tzinfo=timezone.utc)
        tags = (BlogTag(name="python", path="/tags/python/"),)
        posts = [
            _post(1, tie, title="Tie1"),
            _post(2, new, title="New", slug="sm", tags=tags),
            _post(3, tie, title="Tie3"),
            *[_post(n, old, title=f"P{n}") for n in range(4, 22)],
        ]
        pages = BlogArchiveBuilder(_settings(page_size=10)).build(posts)

        # Order: desc by published_at, tie-break by issue_number desc.
        titles = [e.title for e in pages[0].entries]
        assert titles[0] == "New"  # 2024-07-01
        assert titles[1] == "Tie3"  # same ts, higher number
        assert titles[2] == "Tie1"  # same ts, lower number

        # Detail and tag links pre-computed from BlogPost.
        entry = pages[0].entries[0]
        assert entry.issue_number == 2
        assert entry.detail_path == "/blog/sm/"
        assert entry.tags == tags

        # Slices: 10 + 10 + 1.
        assert [len(p.entries) for p in pages] == [10, 10, 1]

        # Routes: page 1 is /blog/, pages 2-3 use /blog/page/N/.
        assert pages[0].route == ArchivePageRoute(
            canonical_path="/blog/", output_path="blog/index.html"
        )
        assert pages[1].route == ArchivePageRoute(
            canonical_path="/blog/page/2/", output_path="blog/page/2/index.html"
        )
        assert pages[2].canonical_url == "https://example.com/blog/page/3/"

        # Prev/next linkage.
        assert pages[0].prev_route is None
        assert pages[0].next_route == pages[1].route
        assert pages[1].prev_route == pages[0].route
        assert pages[1].next_route == pages[2].route
        assert pages[2].prev_route == pages[1].route
        assert pages[2].next_route is None

    def test_boundary_zero_ten_eleven(self) -> None:
        """Boundary: 0 posts -> one intentional page; 10 -> one full page;
        11 -> two pages (10 + 1)."""
        # 0
        empty = BlogArchiveBuilder(_settings(page_size=10)).build([])
        assert len(empty) == 1
        assert empty[0].entries == ()
        assert empty[0].page_number == empty[0].total_pages == 1
        assert empty[0].prev_route is None and empty[0].next_route is None

        # 10
        ten = BlogArchiveBuilder(_settings(page_size=10)).build(_posts(10))
        assert len(ten) == 1
        assert len(ten[0].entries) == 10

        # 11
        eleven = BlogArchiveBuilder(_settings(page_size=10)).build(_posts(11))
        assert [len(p.entries) for p in eleven] == [10, 1]

        # Default page_size is 10.
        assert _settings().paths.page_size == 10


@pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
def test_theme_strict_renderer_and_writer_tracer(theme: str, tmp_path: Path) -> None:
    """Strict renderer consumes only ArchivePage; writer tracer writes
    directory-index paths from route.output_path."""
    tags = (BlogTag(name="python", path="/tags/python/"),)
    page = BlogArchiveBuilder(_settings(theme=theme, page_size=10)).build(
        [_post(1, datetime(2024, 1, 1, tzinfo=timezone.utc), slug="sm", tags=tags)]
    )[0]

    html = _render(theme).render_blog_archive(page)
    assert "Post 1" in html
    assert 'href="/blog/sm/"' in html
    assert 'href="/tags/python/"' in html
    assert 'href="https://example.com/blog/"' in html

    # Empty page renders intentional state.
    empty_html = _render(theme).render_blog_archive(
        BlogArchiveBuilder(_settings(theme=theme)).build([])[0]
    )
    assert 'class="empty-state"' in empty_html

    # Writer tracer: 11 posts -> 2 directory-index files.
    pages = BlogArchiveBuilder(_settings(theme=theme, page_size=10)).build(_posts(11))
    written = write_archive_pages(pages, _render(theme).render_blog_archive, tmp_path)
    assert written == (
        tmp_path / "blog/index.html",
        tmp_path / "blog/page/2/index.html",
    )
    assert all(p.exists() for p in written)
    assert not (tmp_path / "blog/page/2.html").exists()
