"""Tests for RenderService public contract."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from github_blog.services.render_service import RenderService

_PROJECT_ROOT = Path(__file__).parent.parent.absolute()


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
    issue.labels = []
    if labels:
        for name in labels:
            m = MagicMock()
            m.name = name
            issue.labels.append(m)
    issue.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    issue.updated_at = datetime(2024, 1, 2, tzinfo=timezone.utc)
    return issue


def test_markdown_contract() -> None:
    """Markdown rendering: bold, lazy images, tag-link stripping, normal links."""
    render = _render_service()

    # Bold.
    assert "<strong>world</strong>" in render.markdown_to_html("Hello **world**")

    # Lazy loading on images.
    assert '<img loading="lazy"' in render.markdown_to_html(
        "![alt](https://example.com/img.png)"
    )

    # Tag new-issue links stripped to plain text.
    md = (
        "Tags: [#blog](https://github.com/geoqiao/geoqiao.github.io/issues/new#blog) "
        "and [rye](https://github.com/mitsuhiko/rye)"
    )
    html = render.markdown_to_html(md)
    assert "#blog" in html
    assert '<a href="https://github.com/mitsuhiko/rye">rye</a>' in html
    assert "issues/new" not in html


@pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
def test_legacy_render_post_contract(theme: str) -> None:
    """Legacy render_post: malicious HTML sanitized, .html canonical/tag
    hrefs, SEO description fallback, issue/repo comments binding."""
    render = _render_service(theme)
    issue = _make_issue(number=42, title="Legacy Post", labels=["python", "web"])

    # Malicious HTML is sanitized by render_post (body content only).
    html = render.render_post(
        issue, slug="1-test", html_body="<script>alert(1)</script><p>safe</p>"
    )
    assert "alert(1)" not in html
    assert "safe" in html

    # Legacy .html canonical path (not strict /slug/).
    assert "/blog/1-test.html" in html
    assert "/blog/1-test/" not in html

    # Legacy .html tag hrefs (not strict /tags/).
    assert 'href="/tag/python.html"' in html
    assert 'href="/tag/web.html"' in html
    assert "/tags/python/" not in html

    # SEO description fallback to settings.site.description.
    assert 'content="Test Description"' in html
    assert '<meta property="og:description" content="Test Description"' in html

    # Utterances comments bind issue number and repo.
    assert "issue-number" in html
    assert "42" in html
    assert "{{ comments.repo }}" not in html  # template variable resolved
    assert "{{ post.issue_number }}" not in html

    # Theme mode auto + postMessage + MutationObserver + Safari workaround.
    assert "commentsThemeMode" in html
    assert "auto" in html
    assert "postMessage" in html
    assert "MutationObserver" in html
    assert "insertAdjacentHTML" in html
    assert 'loading="lazy"' in html or "loading='lazy'" in html


def test_legacy_rss_xml() -> None:
    """Legacy generate_rss produces valid XML with .html entry URLs."""
    render = _render_service()
    issues = [_make_issue(number=1)]
    rss = render.generate_rss(issues, {"1": "1-test"})
    assert "/blog/1-test.html" in rss
    assert "<feed" in rss or "<atom" in rss.lower()


def test_sitemap_and_robots() -> None:
    """Sitemap contains .html blog URLs; robots references the site origin."""
    render = _render_service()
    issues = [_make_issue(number=1)]
    sitemap = render.render_sitemap(issues, {"1": "1-test"}, tags=["python"])
    assert "/blog/1-test.html" in sitemap
    assert "https://example.com" in sitemap

    robots = render.render_robots()
    assert "https://example.com" in robots
