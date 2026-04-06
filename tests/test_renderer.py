from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from github_blog.services.render_service import RenderService


@pytest.fixture
def render():
    project_root = Path(__file__).parent.parent.absolute()
    settings = MagicMock()
    settings.paths.theme_path = project_root / "templates" / "Escape1"
    settings.paths.seo_path = project_root / "templates" / "seo"
    settings.paths.theme_url_path = "/templates/Escape1"
    settings.paths.language = "en"
    settings.paths.rss = "atom.xml"
    settings.paths.blog = "blog"
    settings.paths.home_post_count = 10
    settings.blog.title = "Test Blog"
    settings.blog.url = "https://example.com"
    settings.blog.author = "Author"
    settings.blog.description = "Test Description"
    settings.github.username = "user"
    settings.github.repo = "user/repo"
    settings.seo.google_search_console = ""
    settings.about.avatar = ""
    settings.about.bio = "Test bio"
    settings.about.expertise = ["Skill 1", "Skill 2"]
    settings.about.links = []
    settings.navigation.items = []
    settings.branding.show_powered_by = True
    settings.branding.powered_by_text = "Powered by"
    settings.branding.powered_by_url = "https://github.com/geoqiao/github-blog"
    settings.branding.show_intro = False
    settings.branding.intro_text = ""
    settings.branding.intro_text2 = "Generated with Python + Jinja2, deployed via GitHub Actions."
    settings.branding.source_link_text = "View Source"
    settings.branding.source_link_url = ""
    settings.comments.provider = "utterances"
    settings.comments.repo = ""
    settings.comments.theme = "github-light"
    settings.comments.theme_mode = "auto"
    return RenderService(settings)


def _make_issue(number=1, title="Test Post", body="Hello **world**", labels=None):
    issue = MagicMock()
    issue.number = number
    issue.title = title
    issue.body = body
    issue.labels = labels or []
    issue.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    issue.updated_at = datetime(2024, 1, 2, tzinfo=timezone.utc)
    return issue


def test_markdown_to_html_renders_bold(render):
    html = render.markdown_to_html("Hello **world**")
    assert "<strong>world</strong>" in html


def test_render_post_contains_title(render):
    issue = _make_issue(title="My Great Post")
    html = render.render_post(issue, slug="1-test", html_body="<p>body</p>")
    assert "My Great Post" in html


def test_render_post_contains_toc_element(render):
    issue = _make_issue()
    html = render.render_post(issue, slug="1-test", html_body="<p>body</p>")
    assert 'id="toc"' in html


def test_render_index_contains_issues(render):
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


def test_render_home_shows_latest_posts(render):
    issues = [_make_issue(number=i, title=f"Post {i}") for i in range(1, 4)]
    html = render.render_home(
        issues, issue_slugs={str(i): f"{i}-test" for i in range(1, 4)}
    )
    assert "Post 1" in html
    assert "/blog/1-test.html" in html


def test_render_tag_page_contains_tag_name(render):
    issues = [_make_issue(title="Tagged Post")]
    html = render.render_tag_page(
        "python", issues, tags=["python"], issue_slugs={"1": "1-python"}
    )
    assert "python" in html.lower()
    assert "/blog/1-python.html" in html


def test_image_has_lazy_loading(render):
    html = render.markdown_to_html("![alt text](https://example.com/img.png)")
    assert '<img loading="lazy"' in html


def test_render_index_pagination(render):
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


def test_render_post_no_labels(render):
    issue = _make_issue(labels=[])
    html = render.render_post(issue, slug="1-test", html_body="<p>body</p>")
    assert "Tags:" not in html


def test_render_rss_contains_slug(render):
    issues = [_make_issue(number=1)]
    issue_slugs = {"1": "1-test"}
    rss = render.generate_rss(issues, issue_slugs)
    assert "/blog/1-test.html" in rss


def test_render_sitemap_contains_slug(render):
    issues = [_make_issue(number=1)]
    issue_slugs = {"1": "1-test"}
    sitemap = render.render_sitemap(issues, issue_slugs, tags=["python"])
    assert "/blog/1-test.html" in sitemap


def test_branding_injected_to_context(render):
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


def test_comments_uses_github_repo_when_empty(render):
    """Verify comments.repo falls back to github.repo when empty."""
    context = render._get_common_context()
    assert "comments" in context
    comments = context["comments"]
    assert "provider" in comments
    assert "repo" in comments
    assert "theme" in comments
    # repo should fall back to github.repo when comments.repo is empty
    assert comments["repo"] == render.settings.github.repo
