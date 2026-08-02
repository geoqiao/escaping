"""Template integrity tests for Escape1 and Escape2 themes."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

from github_blog.models.blog_archive import ArchiveEntry, ArchivePage, ArchivePageRoute
from github_blog.models.blog_post import BlogPost, BlogTag

PROJECT_ROOT = Path(__file__).parent.parent.absolute()
THEME = "Escape1"

REQUIRED_TEMPLATES = [
    "base.html",
    "home.html",
    "post.html",
    "index.html",
    "tag.html",
    "tags.html",
    "about.html",
]


class MockNavigation:
    """Mock navigation object matching NavigationConfig structure."""

    def __init__(self) -> None:
        self.items = []


@pytest.fixture
def full_context() -> dict[str, object]:
    return {
        "blog_title": "Test Blog",
        "blog_url": "https://test.com",
        "author_name": "Test Author",
        "meta_description": "Test description",
        "github_name": "testuser",
        "github_repo": "testuser/testrepo",
        "theme_path": "/templates/Escape1",
        "language": "en",
        "skip_link_text": "Skip to main content",
        "rss_atom_path": "atom.xml",
        "about_avatar": "",
        "about_bio": "Test bio",
        "about_expertise": [],
        "about_links": [],
        "navigation": MockNavigation(),
        "google_search_verification": "",
        "branding": {
            "show_powered_by": True,
            "powered_by_text": "github_blog",
            "powered_by_url": "https://github.com/geoqiao/github-blog",
            "show_intro": True,
            "intro_text": "This is a static blog system.",
            "source_link_text": "View source code →",
            "source_link_url": "https://github.com/geoqiao/github-blog",
        },
        "comments": {
            "provider": "utterances",
            "repo": "testuser/testrepo",
            "theme": "github-light",
            "theme_mode": "auto",
        },
    }


def _make_blog_post() -> BlogPost:
    """Create a BlogPost for template rendering tests."""
    return BlogPost(
        issue_number=1,
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


def _make_archive_page() -> ArchivePage:
    """Create an internal ArchivePage for index template tests."""
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


def test_all_required_templates_exist() -> None:
    """Verify all required templates exist."""
    theme_path = PROJECT_ROOT / "templates" / THEME
    for template in REQUIRED_TEMPLATES:
        assert (theme_path / template).exists()


def test_base_template_has_branding_footer(full_context: dict[str, object]) -> None:
    """Verify base.html uses branding variables."""
    theme_path = PROJECT_ROOT / "templates" / THEME
    env = Environment(loader=FileSystemLoader(str(theme_path)), autoescape=True)
    template = env.get_template("base.html")
    html = template.render(**full_context)
    assert "github_blog" in html


def test_home_template_has_branding_intro(full_context: dict[str, object]) -> None:
    """Verify home.html uses branding variables."""
    theme_path = PROJECT_ROOT / "templates" / THEME
    env = Environment(loader=FileSystemLoader(str(theme_path)), autoescape=True)
    template = env.get_template("home.html")
    full_context["issues"] = []
    full_context["issue_slugs"] = {}
    html = template.render(**full_context)
    assert "github_blog" in html


def test_all_templates_render(full_context: dict[str, object]) -> None:
    """Verify all templates render without errors."""
    theme_path = PROJECT_ROOT / "templates" / THEME
    env = Environment(loader=FileSystemLoader(str(theme_path)), autoescape=True)

    mock_issue = type(
        "MockIssue",
        (),
        {
            "number": 1,
            "title": "Test",
            "body": "Body",
            "labels": [],
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        },
    )()

    for template_name in REQUIRED_TEMPLATES:
        template = env.get_template(template_name)
        ctx = dict(full_context)

        if template_name == "post.html":
            ctx.update({"post": _make_blog_post()})
        elif template_name == "index.html":
            ctx.update({"archive_page": _make_archive_page()})
        elif template_name == "tag.html":
            ctx.update(
                {
                    "issues": [mock_issue],
                    "issue_slugs": {"1": "1-test"},
                    "tags": ["python"],
                }
            )
        elif template_name == "tags.html":
            ctx.update(
                {"tags": ["python"], "tag_items": [{"name": "python", "count": 1}]}
            )
        elif template_name == "home.html":
            ctx.update({"issues": [mock_issue], "issue_slugs": {"1": "1-test"}})

        html = template.render(**ctx)
        assert isinstance(html, str), f"{template_name} failed"


def test_escape1_post_description_block_overridden() -> None:
    """Escape1 post.html must override the base description block."""
    theme_path = PROJECT_ROOT / "templates" / THEME
    env = Environment(loader=FileSystemLoader(str(theme_path)), autoescape=True)
    template = env.get_template("post.html")
    post = BlogPost(
        issue_number=1,
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
    ctx: dict[str, object] = {
        "blog_title": "Test Blog",
        "blog_url": "https://test.com",
        "author_name": "Test Author",
        "meta_description": "Site description",
        "github_name": "testuser",
        "github_repo": "testuser/testrepo",
        "theme_path": "/templates/Escape1",
        "language": "en",
        "skip_link_text": "Skip to main content",
        "rss_atom_path": "atom.xml",
        "about_avatar": "",
        "about_bio": "",
        "about_expertise": [],
        "about_links": [],
        "navigation": MockNavigation(),
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
        "post": post,
    }
    html = template.render(**ctx)
    assert 'content="My validated meta description."' in html


class TestEscape2Templates:
    """Template integrity tests for Escape2 theme."""

    @pytest.fixture
    def full_context_e2(self) -> dict[str, object]:
        return {
            "blog_title": "Test Blog",
            "blog_url": "https://test.com",
            "author_name": "Test Author",
            "meta_description": "Test description",
            "github_name": "testuser",
            "github_repo": "testuser/testrepo",
            "theme_path": "/templates/Escape2",
            "language": "en",
            "skip_link_text": "Skip to main content",
            "rss_atom_path": "atom.xml",
            "about_avatar": "",
            "about_bio": "Test bio",
            "about_expertise": [],
            "about_links": [],
            "navigation": MockNavigation(),
            "google_search_verification": "",
            "branding": {
                "show_powered_by": True,
                "powered_by_text": "github_blog",
                "powered_by_url": "https://github.com/geoqiao/github-blog",
                "show_intro": True,
                "intro_text": "This is a static blog system.",
                "source_link_text": "View source code →",
                "source_link_url": "https://github.com/geoqiao/github-blog",
            },
            "comments": {
                "provider": "utterances",
                "repo": "testuser/testrepo",
                "theme": "github-light",
                "theme_mode": "auto",
            },
        }

    def _make_blog_post(self) -> BlogPost:
        """Create a BlogPost for Escape2 template rendering tests."""
        return BlogPost(
            issue_number=1,
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

    def test_all_required_templates_exist(self) -> None:
        theme_path = PROJECT_ROOT / "templates" / "Escape2"
        for template in REQUIRED_TEMPLATES:
            assert (theme_path / template).exists()

    def test_base_template_has_branding_footer(
        self, full_context_e2: dict[str, object]
    ) -> None:
        theme_path = PROJECT_ROOT / "templates" / "Escape2"
        env = Environment(loader=FileSystemLoader(str(theme_path)), autoescape=True)
        template = env.get_template("base.html")
        html = template.render(**full_context_e2)
        assert "github_blog" in html

    def test_home_template_has_branding_intro(
        self, full_context_e2: dict[str, object]
    ) -> None:
        theme_path = PROJECT_ROOT / "templates" / "Escape2"
        env = Environment(loader=FileSystemLoader(str(theme_path)), autoescape=True)
        template = env.get_template("home.html")
        full_context_e2["issues"] = []
        full_context_e2["issue_slugs"] = {}
        html = template.render(**full_context_e2)
        assert "github_blog" in html

    def test_all_templates_render(self, full_context_e2: dict[str, object]) -> None:
        theme_path = PROJECT_ROOT / "templates" / "Escape2"
        env = Environment(loader=FileSystemLoader(str(theme_path)), autoescape=True)

        mock_issue = type(
            "MockIssue",
            (),
            {
                "number": 1,
                "title": "Test",
                "body": "Body",
                "labels": [],
                "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
                "updated_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
            },
        )()

        for template_name in REQUIRED_TEMPLATES:
            template = env.get_template(template_name)
            ctx = dict(full_context_e2)

            if template_name == "post.html":
                ctx.update({"post": self._make_blog_post()})
            elif template_name == "index.html":
                ctx.update({"archive_page": _make_archive_page()})
            elif template_name == "tag.html":
                ctx.update(
                    {
                        "issues": [mock_issue],
                        "issue_slugs": {"1": "1-test"},
                        "tags": ["python"],
                    }
                )
            elif template_name == "tags.html":
                ctx.update(
                    {"tags": ["python"], "tag_items": [{"name": "python", "count": 1}]}
                )
            elif template_name == "home.html":
                ctx.update({"issues": [mock_issue], "issue_slugs": {"1": "1-test"}})

            html = template.render(**ctx)
            assert isinstance(html, str), f"{template_name} failed"

    def test_post_description_block_overridden(self) -> None:
        """Escape2 post.html must override the base description block."""
        theme_path = PROJECT_ROOT / "templates" / "Escape2"
        env = Environment(loader=FileSystemLoader(str(theme_path)), autoescape=True)
        template = env.get_template("post.html")
        post = BlogPost(
            issue_number=1,
            title="Test Post",
            slug="test-post",
            description="My Escape2 meta description.",
            created_date="2026-01-15",
            published_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
            updated_at=datetime(2026, 1, 16, tzinfo=timezone.utc),
            tags=(BlogTag(name="python", path="/tags/python/"),),
            body_html="<p>Body.</p>",
            canonical_path="/blog/test-post/",
        )
        ctx: dict[str, object] = {
            "blog_title": "Test Blog",
            "blog_url": "https://test.com",
            "author_name": "Test Author",
            "meta_description": "Site description",
            "github_name": "testuser",
            "github_repo": "testuser/testrepo",
            "theme_path": "/templates/Escape2",
            "language": "en",
            "skip_link_text": "Skip to main content",
            "rss_atom_path": "atom.xml",
            "about_avatar": "",
            "about_bio": "",
            "about_expertise": [],
            "about_links": [],
            "navigation": MockNavigation(),
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
            "post": post,
        }
        html = template.render(**ctx)
        assert 'content="My Escape2 meta description."' in html
        assert (
            "Site description"
            not in html.split('<meta name="description"')[1].split(">")[0]
            if '<meta name="description"' in html
            else True
        )

    def test_post_theme_mode_auto_postmessage(self) -> None:
        """Escape2 post.html must have postMessage + MutationObserver for auto mode."""
        theme_path = PROJECT_ROOT / "templates" / "Escape2"
        env = Environment(loader=FileSystemLoader(str(theme_path)), autoescape=True)
        template = env.get_template("post.html")
        post = BlogPost(
            issue_number=1,
            title="Test Post",
            slug="test-post",
            description="desc",
            created_date="2026-01-15",
            published_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
            updated_at=datetime(2026, 1, 16, tzinfo=timezone.utc),
            tags=(),
            body_html="<p>Body.</p>",
            canonical_path="/blog/test-post/",
        )
        ctx: dict[str, object] = {
            "blog_title": "Test Blog",
            "blog_url": "https://test.com",
            "author_name": "Test Author",
            "meta_description": "desc",
            "github_name": "testuser",
            "github_repo": "testuser/testrepo",
            "theme_path": "/templates/Escape2",
            "language": "en",
            "skip_link_text": "Skip to main content",
            "rss_atom_path": "atom.xml",
            "about_avatar": "",
            "about_bio": "",
            "about_expertise": [],
            "about_links": [],
            "navigation": MockNavigation(),
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
            "post": post,
        }
        html = template.render(**ctx)
        assert "commentsThemeMode" in html
        assert "auto" in html
        assert "postMessage" in html
        assert "MutationObserver" in html

    def test_post_safari_lazy_iframe_workaround(self) -> None:
        """Escape2 post.html must have Safari lazy-iframe workaround."""
        theme_path = PROJECT_ROOT / "templates" / "Escape2"
        env = Environment(loader=FileSystemLoader(str(theme_path)), autoescape=True)
        template = env.get_template("post.html")
        post = BlogPost(
            issue_number=1,
            title="Test Post",
            slug="test-post",
            description="desc",
            created_date="2026-01-15",
            published_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
            updated_at=datetime(2026, 1, 16, tzinfo=timezone.utc),
            tags=(),
            body_html="<p>Body.</p>",
            canonical_path="/blog/test-post/",
        )
        ctx: dict[str, object] = {
            "blog_title": "Test Blog",
            "blog_url": "https://test.com",
            "author_name": "Test Author",
            "meta_description": "desc",
            "github_name": "testuser",
            "github_repo": "testuser/testrepo",
            "theme_path": "/templates/Escape2",
            "language": "en",
            "skip_link_text": "Skip to main content",
            "rss_atom_path": "atom.xml",
            "about_avatar": "",
            "about_bio": "",
            "about_expertise": [],
            "about_links": [],
            "navigation": MockNavigation(),
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
            "post": post,
        }
        html = template.render(**ctx)
        assert "insertAdjacentHTML" in html
        assert 'loading="lazy"' in html or "loading='lazy'" in html
