"""Template integrity tests for Escape1 and Escape2 themes."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from github_blog.models.blog_archive import ArchiveEntry, ArchivePage, ArchivePageRoute
from github_blog.models.blog_post import BlogPost, BlogTag
from github_blog.models.home_page import (
    HomeNavigationLink,
    HomePage,
    HomePostEntry,
    HomeProfile,
    HomeProfileLink,
    HomeRoute,
)
from github_blog.models.tag_taxonomy import (
    TagArchive,
    TagArchiveEntry,
    TagArchiveRoute,
    TagsIndex,
    TagsIndexRoute,
    TagSummary,
)

PROJECT_ROOT = Path(__file__).parent.parent.absolute()

REQUIRED_TEMPLATES = [
    "base.html",
    "home.html",
    "post.html",
    "index.html",
    "tag.html",
    "tags.html",
    "about.html",
]


class _MockNav:
    def __init__(self) -> None:
        self.items = []


def _full_context(theme: str) -> dict[str, object]:
    return {
        "blog_title": "Test Blog",
        "blog_url": "https://test.com",
        "author_name": "Test Author",
        "meta_description": "Test description",
        "github_name": "testuser",
        "github_repo": "testuser/testrepo",
        "theme_path": f"/templates/{theme}",
        "language": "en",
        "skip_link_text": "Skip to main content",
        "rss_atom_path": "atom.xml",
        "about_avatar": "",
        "about_bio": "Test bio",
        "about_expertise": [],
        "about_links": [],
        "navigation": _MockNav(),
        "navigation_items": [],
        "google_search_verification": "",
        "branding": {
            "show_powered_by": True,
            "powered_by_text": "github_blog",
            "powered_by_url": "https://github.com/geoqiao/github-blog",
            "show_intro": False,
            "intro_text": "",
            "source_link_text": "",
            "source_link_url": "",
        },
        "comments": {
            "provider": "utterances",
            "repo": "testuser/testrepo",
            "theme": "github-light",
            "theme_mode": "auto",
        },
    }


def _blog_post() -> BlogPost:
    return BlogPost(
        issue_number=42,
        title="Test Post",
        slug="test-post",
        description="A test post for rendering.",
        created_date="2026-01-15",
        published_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 16, tzinfo=timezone.utc),
        tags=(
            BlogTag(name="python", path="/tags/python/"),
            BlogTag(name="web", path="/tags/web/"),
        ),
        body_html="<p>Test body content.</p>",
        canonical_path="/blog/test-post/",
    )


def _archive_page() -> ArchivePage:
    return ArchivePage(
        page_number=1,
        total_pages=1,
        route=ArchivePageRoute("/blog/", "blog/index.html"),
        canonical_url="https://test.com/blog/",
        prev_route=None,
        next_route=None,
        entries=(
            ArchiveEntry(
                title="Test",
                created_date="2024-01-01",
                detail_path="/blog/test/",
                tags=(BlogTag(name="python", path="/tags/python/"),),
            ),
        ),
    )


def _home_page() -> HomePage:
    return HomePage(
        route=HomeRoute(canonical_path="/", output_path="index.html"),
        canonical_url="https://test.com/",
        site_title="Test Blog",
        site_author="Test Author",
        site_description="Test description",
        profile=HomeProfile(
            avatar="",
            bio="Test bio",
            links=(HomeProfileLink(name="GitHub", url="https://github.com/test"),),
        ),
        navigation=(HomeNavigationLink(name="Blog", url="/blog/"),),
        recent_posts=(
            HomePostEntry(
                title="Test Post",
                created_date="2024-01-01",
                detail_path="/blog/test-post/",
                tags=(BlogTag(name="python", path="/tags/python/"),),
            ),
        ),
    )


def _tags_index() -> TagsIndex:
    return TagsIndex(
        route=TagsIndexRoute(canonical_path="/tags/", output_path="tags/index.html"),
        canonical_url="https://test.com/tags/",
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


def _tag_archive() -> TagArchive:
    return TagArchive(
        route=TagArchiveRoute(
            canonical_path="/tags/python/", output_path="tags/python/index.html"
        ),
        canonical_url="https://test.com/tags/python/",
        tag_name="python",
        index_route=TagsIndexRoute(
            canonical_path="/tags/", output_path="tags/index.html"
        ),
        entries=(
            TagArchiveEntry(
                title="Test",
                created_date="2024-01-01",
                detail_path="/blog/test/",
                tags=(BlogTag(name="python", path="/tags/python/"),),
            ),
        ),
    )


def _model_for(template_name: str) -> dict[str, object]:
    if template_name == "post.html":
        return {"post": _blog_post()}
    if template_name == "index.html":
        return {"archive_page": _archive_page()}
    if template_name == "tag.html":
        return {"tag_archive": _tag_archive()}
    if template_name == "tags.html":
        return {"tags_index": _tags_index()}
    if template_name == "home.html":
        return {"home_page": _home_page()}
    return {}


@pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
def test_required_files_exist(theme: str) -> None:
    theme_path = PROJECT_ROOT / "templates" / theme
    for template in REQUIRED_TEMPLATES:
        assert (theme_path / template).exists(), f"{theme}/{template} missing"


@pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
def test_all_templates_render_with_public_models(theme: str) -> None:
    """Every required template renders without error using the public
    internal models and common context."""
    theme_path = PROJECT_ROOT / "templates" / theme
    env = Environment(loader=FileSystemLoader(str(theme_path)), autoescape=True)
    ctx = _full_context(theme)

    for template_name in REQUIRED_TEMPLATES:
        template = env.get_template(template_name)
        model_ctx = _model_for(template_name)
        html = template.render(**ctx, **model_ctx)
        assert isinstance(html, str), f"{theme}/{template_name} failed to render"


@pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
def test_post_critical_contract(theme: str) -> None:
    """Post template critical contract for both themes: issue/repo binding,
    postMessage, MutationObserver, insertAdjacentHTML, loading=lazy removal,
    SEO description, static resource absolute URL, configured language."""
    theme_path = PROJECT_ROOT / "templates" / theme
    env = Environment(loader=FileSystemLoader(str(theme_path)), autoescape=True)
    template = env.get_template("post.html")
    post = BlogPost(
        issue_number=42,
        title="Test Post",
        slug="test-post",
        description="My validated meta description.",
        created_date="2026-01-15",
        published_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 16, tzinfo=timezone.utc),
        tags=(BlogTag(name="python", path="/tags/python/"),),
        body_html="<p>Body.</p>",
        canonical_path="/blog/test-post/",
    )
    ctx = _full_context(theme)
    ctx["post"] = post
    html = template.render(**ctx)

    # issue/repo binding: utterances script binds issue-number and comments.repo.
    assert "issue-number" in html
    assert "42" in html
    assert "{{ comments.repo }}" not in html
    assert "testuser/testrepo" in html

    # postMessage + MutationObserver for theme_mode auto.
    assert "commentsThemeMode" in html
    assert "auto" in html
    assert "postMessage" in html
    assert "MutationObserver" in html

    # insertAdjacentHTML + loading="lazy" removal (Safari workaround).
    assert "insertAdjacentHTML" in html
    assert 'loading="lazy"' in html or "loading='lazy'" in html

    # SEO description uses post.description, not site-level meta_description.
    assert 'content="My validated meta description."' in html

    # Static resources use absolute URL via {{ theme_path }} (starts with /).
    assert f"/templates/{theme}/static/" in html

    # Configured language appears in <html lang="...">.
    assert 'lang="en"' in html
