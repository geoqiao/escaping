from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from github_blog.models.blog_post import BlogPost, BlogTag
from github_blog.services.render_service import RenderService


@pytest.fixture
def render() -> Any:  # noqa: ANN401
    project_root = Path(__file__).parent.parent.absolute()
    settings = MagicMock()
    settings.paths.theme_path = project_root / "templates" / "Escape1"
    settings.paths.seo_path = project_root / "templates" / "seo"
    settings.paths.theme_url_path = "/templates/Escape1"
    settings.paths.rss = "atom.xml"
    settings.paths.blog = "blog"
    settings.paths.tag = "tag"
    settings.paths.page = "page"
    settings.site.title = "Test Blog"
    settings.site.url = "https://example.com"
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


def _make_issue(
    number: int = 1,
    title: str = "Test Post",
    body: str = "Hello **world**",
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
    issue.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    issue.updated_at = datetime(2024, 1, 2, tzinfo=timezone.utc)
    return issue


def test_markdown_to_html_renders_bold(render: RenderService) -> None:
    html = render.markdown_to_html("Hello **world**")
    assert "<strong>world</strong>" in html


def test_render_post_contains_title(render: RenderService) -> None:
    issue = _make_issue(title="My Great Post")
    html = render.render_post(issue, slug="1-test", html_body="<p>body</p>")
    assert "My Great Post" in html


def test_render_post_contains_toc_element(render: RenderService) -> None:
    issue = _make_issue()
    html = render.render_post(issue, slug="1-test", html_body="<p>body</p>")
    assert 'id="toc"' in html


def test_render_post_no_labels(render: RenderService) -> None:
    issue = _make_issue(labels=[])
    html = render.render_post(issue, slug="1-test", html_body="<p>body</p>")
    assert "Tags:" not in html


def test_render_post_legacy_canonical_path(render: RenderService) -> None:
    """render_post() must produce legacy .html canonical path, not strict /slug/.

    The legacy adapter creates a BlogPost whose canonical_path matches the
    legacy ``.html`` file writer so production pages are not
    self-contradictory.  The strict ``/{slug}/`` path belongs to the
    BlogCompiler route, not the legacy pipeline.
    """
    issue = _make_issue(number=1, title="Legacy Post")
    html = render.render_post(issue, slug="1-legacy-post", html_body="<p>body</p>")
    assert "/blog/1-legacy-post.html" in html
    # Strict canonical (/blog/{slug}/) must NOT appear in legacy detail pages
    assert "/blog/1-legacy-post/" not in html


def test_render_index_contains_issues(render: RenderService) -> None:
    issues = [
        _make_issue(number=1, title="Post One"),
        _make_issue(number=2, title="Post Two"),
    ]
    pagination = {
        "page": 1,
        "pages": 1,
        "has_prev": False,
        "has_next": False,
        "prev_num": 0,
        "next_num": 2,
    }
    html = render.render_index(
        issues,
        tags=["python"],
        pagination=pagination,
        issue_slugs={"1": "1-python", "2": "2-python"},
    )
    assert "Post One" in html
    assert "Post Two" in html
    assert "/blog/1-python.html" in html
    assert "/blog/2-python.html" in html


def test_render_home_shows_latest_posts(render: RenderService) -> None:
    issues = [_make_issue(number=i, title=f"Post {i}") for i in range(1, 4)]
    html = render.render_home(
        issues, issue_slugs={str(i): f"{i}-test" for i in range(1, 4)}
    )
    assert "Post 1" in html
    assert "/blog/1-test.html" in html


def test_render_tag_page_contains_tag_name(render: RenderService) -> None:
    issues = [_make_issue(title="Tagged Post")]
    html = render.render_tag_page(
        "python", issues, tags=["python"], issue_slugs={"1": "1-python"}
    )
    assert "python" in html.lower()
    assert "/blog/1-python.html" in html


def test_image_has_lazy_loading(render: RenderService) -> None:
    html = render.markdown_to_html("![alt text](https://example.com/img.png)")
    assert '<img loading="lazy"' in html


def test_markdown_to_html_strips_tag_new_issue_links(render: RenderService) -> None:
    md = "Tags: [#blog](https://github.com/geoqiao/geoqiao.github.io/issues/new#blog) [#python](https://github.com/geoqiao/geoqiao.github.io/issues/new?label=python)"
    html = render.markdown_to_html(md)
    assert "#blog" in html
    assert "#python" in html
    assert (
        '<a href="https://github.com/geoqiao/geoqiao.github.io/issues/new' not in html
    )
    assert "<a" not in html


def test_markdown_to_html_keeps_normal_links(render: RenderService) -> None:
    md = "See [rye](https://github.com/mitsuhiko/rye) and [#blog](https://github.com/geoqiao/geoqiao.github.io/issues/new#blog)"
    html = render.markdown_to_html(md)
    assert '<a href="https://github.com/mitsuhiko/rye">rye</a>' in html
    assert "#blog" in html
    assert (
        '<a href="https://github.com/geoqiao/geoqiao.github.io/issues/new' not in html
    )


def test_render_index_pagination(render: RenderService) -> None:
    issues = [_make_issue(number=i) for i in range(1, 11)]
    pagination = {
        "page": 1,
        "pages": 2,
        "has_prev": False,
        "has_next": True,
        "prev_num": 0,
        "next_num": 2,
    }
    html = render.render_index(
        issues,
        tags=["python"],
        pagination=pagination,
        issue_slugs={str(i): f"{i}-test" for i in range(1, 11)},
    )
    assert 'class="pagination"' in html
    assert 'href="/blog/page/2.html"' in html
    assert 'class="pagination-prev disabled"' in html


def test_render_rss_contains_slug(render: RenderService) -> None:
    issues = [_make_issue(number=1)]
    issue_slugs = {"1": "1-test"}
    rss = render.generate_rss(issues, issue_slugs)
    assert "/blog/1-test.html" in rss


def test_render_sitemap_contains_slug(render: RenderService) -> None:
    issues = [_make_issue(number=1)]
    issue_slugs = {"1": "1-test"}
    sitemap = render.render_sitemap(issues, issue_slugs, tags=["python"])
    assert "/blog/1-test.html" in sitemap


def test_branding_injected_to_context(render: RenderService) -> None:
    """Verify branding.xxx is in context."""
    context = render._get_common_context()
    assert "branding" in context
    branding = context["branding"]
    assert "show_powered_by" in branding
    assert "powered_by_text" in branding
    assert "powered_by_url" in branding
    assert "show_intro" in branding
    assert "intro_text" in branding
    assert "source_link_text" in branding
    assert "source_link_url" in branding


def test_comments_uses_github_repo_when_empty(render: RenderService) -> None:
    """Verify comments.repo falls back to github.repo when empty."""
    context = render._get_common_context()
    assert "comments" in context
    comments = context["comments"]
    assert "provider" in comments
    assert "repo" in comments
    assert "theme" in comments
    # repo should fall back to github.repo when comments.repo is empty
    assert comments["repo"] == render.settings.github.repo


def _make_blog_post(
    issue_number: int = 1,
    title: str = "Test Post",
    slug: str = "test-post",
    description: str = "A test post.",
    created_date: str = "2026-01-15",
    tags: tuple[BlogTag, ...] = (BlogTag(name="python", path="/tags/python/"),),
    body_html: str = "<p>Body content.</p>",
) -> BlogPost:
    return BlogPost(
        issue_number=issue_number,
        title=title,
        slug=slug,
        description=description,
        created_date=created_date,
        published_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 16, tzinfo=timezone.utc),
        tags=tags,
        body_html=body_html,
        canonical_path=f"/blog/{slug}/",
    )


class TestRenderBlogDetail:
    """Tests for the new BlogPost-based detail rendering."""

    def test_renders_title(self, render: RenderService) -> None:
        post = _make_blog_post(title="My Great Post")
        html = render.render_blog_detail(post)
        assert "My Great Post" in html

    def test_renders_canonical_with_trailing_slash(self, render: RenderService) -> None:
        post = _make_blog_post(slug="my-slug")
        html = render.render_blog_detail(post)
        assert "/blog/my-slug/" in html
        assert "/blog/my-slug.html" not in html

    def test_renders_description_in_og(self, render: RenderService) -> None:
        post = _make_blog_post(description="My custom description.")
        html = render.render_blog_detail(post)
        assert "My custom description." in html

    def test_renders_created_date(self, render: RenderService) -> None:
        post = _make_blog_post(created_date="2026-03-20")
        html = render.render_blog_detail(post)
        assert "2026-03-20" in html

    def test_escape2_labels_authored_date_as_created(self) -> None:
        render = _make_render_service("Escape2")
        post = _make_blog_post(created_date="2020-01-02")
        html = render.render_blog_detail(post)
        assert "<dt>created</dt>" in html
        assert "<dt>published</dt>" not in html

    def test_renders_body_html(self, render: RenderService) -> None:
        post = _make_blog_post(body_html="<p>Hello world.</p>")
        html = render.render_blog_detail(post)
        assert "<p>Hello world.</p>" in html

    def test_renders_tags_with_new_route(self, render: RenderService) -> None:
        post = _make_blog_post(
            tags=(
                BlogTag(name="python", path="/tags/python/"),
                BlogTag(name="rust", path="/tags/rust/"),
            )
        )
        html = render.render_blog_detail(post)
        assert "/tags/python/" in html
        assert "/tags/rust/" in html

    def test_renders_no_tags_when_empty(self, render: RenderService) -> None:
        post = _make_blog_post(tags=())
        html = render.render_blog_detail(post)
        assert "/tags/" not in html

    def test_utterances_binds_issue_number(self, render: RenderService) -> None:
        post = _make_blog_post(issue_number=42)
        html = render.render_blog_detail(post)
        assert "issue-number" in html
        assert "42" in html
        assert "/issues/42" in html or "issues/42" in html

    def test_utterances_preserves_theme_mode_auto(self, render: RenderService) -> None:
        post = _make_blog_post()
        html = render.render_blog_detail(post)
        assert "commentsThemeMode" in html
        assert "auto" in html

    def test_safari_workaround_preserved(self, render: RenderService) -> None:
        post = _make_blog_post()
        html = render.render_blog_detail(post)
        assert 'loading="lazy"' in html or "loading='lazy'" in html
        assert "insertAdjacentHTML" in html

    def test_description_block_overridden(self, render: RenderService) -> None:
        """Validated description drives standard meta description."""
        post = _make_blog_post(description="My validated meta description.")
        html = render.render_blog_detail(post)
        # The meta description should contain the post description, not the
        # site-level meta_description ("Test Description").
        assert "My validated meta description." in html
        # Check it appears in the meta description tag
        assert 'content="My validated meta description."' in html

    def test_toc_element_present(self, render: RenderService) -> None:
        post = _make_blog_post()
        html = render.render_blog_detail(post)
        assert 'id="toc"' in html


# ---------------------------------------------------------------------------
# Legacy render_post adapter: SEO description fallback and tag href
# ---------------------------------------------------------------------------


def _make_render_service(theme: str) -> RenderService:
    """Create a RenderService configured for the given theme."""
    project_root = Path(__file__).parent.parent.absolute()
    settings = MagicMock()
    settings.paths.theme_path = project_root / "templates" / theme
    settings.paths.seo_path = project_root / "templates" / "seo"
    settings.paths.theme_url_path = f"/templates/{theme}"
    settings.paths.rss = "atom.xml"
    settings.paths.blog = "blog"
    settings.paths.tag = "tag"
    settings.paths.page = "page"
    settings.site.title = "Test Blog"
    settings.site.url = "https://example.com"
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


class TestLegacyRenderPostSeoDescription:
    """Legacy render_post must not produce empty SEO description.

    The legacy adapter has no front-matter description, so it must fall
    back to settings.site.description for meta/OG/Twitter.
    """

    def test_escape1_meta_description_non_empty_fallback(self) -> None:
        render = _make_render_service("Escape1")
        issue = _make_issue(number=1, title="Legacy Post")
        html = render.render_post(issue, slug="1-test", html_body="<p>body</p>")
        # meta description must be non-empty and match site description
        assert 'content="Test Description"' in html

    def test_escape1_og_description_non_empty_fallback(self) -> None:
        render = _make_render_service("Escape1")
        issue = _make_issue(number=1, title="Legacy Post")
        html = render.render_post(issue, slug="1-test", html_body="<p>body</p>")
        assert '<meta property="og:description" content="Test Description"' in html

    def test_escape1_twitter_description_non_empty_fallback(self) -> None:
        render = _make_render_service("Escape1")
        issue = _make_issue(number=1, title="Legacy Post")
        html = render.render_post(issue, slug="1-test", html_body="<p>body</p>")
        assert '<meta name="twitter:description" content="Test Description"' in html

    def test_escape2_meta_description_non_empty_fallback(self) -> None:
        render = _make_render_service("Escape2")
        issue = _make_issue(number=1, title="Legacy Post")
        html = render.render_post(issue, slug="1-test", html_body="<p>body</p>")
        assert 'content="Test Description"' in html

    def test_escape2_og_description_non_empty_fallback(self) -> None:
        render = _make_render_service("Escape2")
        issue = _make_issue(number=1, title="Legacy Post")
        html = render.render_post(issue, slug="1-test", html_body="<p>body</p>")
        assert '<meta property="og:description" content="Test Description"' in html

    def test_escape2_twitter_description_non_empty_fallback(self) -> None:
        render = _make_render_service("Escape2")
        issue = _make_issue(number=1, title="Legacy Post")
        html = render.render_post(issue, slug="1-test", html_body="<p>body</p>")
        assert '<meta name="twitter:description" content="Test Description"' in html


class TestLegacyRenderPostTagHref:
    """Legacy render_post tag href must point to the legacy tag file path
    that the BlogGenerator writer produces (/{tag_dir}/{label.name}.html),
    not the strict /tags/{key}/ route.
    """

    def test_escape1_tag_href_uses_legacy_path(self) -> None:
        render = _make_render_service("Escape1")
        issue = _make_issue(number=1, labels=["python", "web"])
        html = render.render_post(issue, slug="1-test", html_body="<p>body</p>")
        assert 'href="/tag/python.html"' in html
        assert 'href="/tag/web.html"' in html
        # Strict tag paths must NOT appear
        assert "/tags/python/" not in html
        assert "/tags/web/" not in html

    def test_escape2_tag_href_uses_legacy_path(self) -> None:
        render = _make_render_service("Escape2")
        issue = _make_issue(number=1, labels=["python", "web"])
        html = render.render_post(issue, slug="1-test", html_body="<p>body</p>")
        assert 'href="/tag/python.html"' in html
        assert 'href="/tag/web.html"' in html
        # Strict tag paths must NOT appear
        assert "/tags/python/" not in html
        assert "/tags/web/" not in html
