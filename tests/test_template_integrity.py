"""Template integrity tests for BearMinimal theme."""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

PROJECT_ROOT = Path(__file__).parent.parent.absolute()
THEME = "BearMinimal"

REQUIRED_TEMPLATES = [
    "base.html", "home.html", "post.html",
    "index.html", "tag.html", "tags.html", "about.html"
]


class MockNavigation:
    """Mock navigation object matching NavigationConfig structure."""
    def __init__(self):
        self.items = []


@pytest.fixture
def full_context():
    return {
        "blog_title": "Test Blog",
        "blog_url": "https://test.com",
        "author_name": "Test Author",
        "meta_description": "Test description",
        "github_name": "testuser",
        "github_repo": "testuser/testrepo",
        "theme_path": "/templates/BearMinimal",
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
        },
    }


def test_all_required_templates_exist():
    """Verify all required templates exist."""
    theme_path = PROJECT_ROOT / "templates" / THEME
    for template in REQUIRED_TEMPLATES:
        assert (theme_path / template).exists()


def test_base_template_has_branding_footer(full_context):
    """Verify base.html uses branding variables."""
    theme_path = PROJECT_ROOT / "templates" / THEME
    env = Environment(loader=FileSystemLoader(str(theme_path)), autoescape=True)
    template = env.get_template("base.html")
    html = template.render(**full_context)
    assert "github_blog" in html


def test_home_template_has_branding_intro(full_context):
    """Verify home.html uses branding variables."""
    theme_path = PROJECT_ROOT / "templates" / THEME
    env = Environment(loader=FileSystemLoader(str(theme_path)), autoescape=True)
    template = env.get_template("home.html")
    full_context["issues"] = []
    full_context["issue_slugs"] = {}
    html = template.render(**full_context)
    assert "github_blog" in html


def test_all_templates_render(full_context):
    """Verify all templates render without errors."""
    theme_path = PROJECT_ROOT / "templates" / THEME
    env = Environment(loader=FileSystemLoader(str(theme_path)), autoescape=True)

    mock_issue = type('MockIssue', (), {
        'number': 1, 'title': 'Test', 'body': 'Body',
        'labels': [], 'created_at': datetime(2024, 1, 1, tzinfo=timezone.utc), 'updated_at': datetime(2024, 1, 1, tzinfo=timezone.utc),
    })()

    for template_name in REQUIRED_TEMPLATES:
        template = env.get_template(template_name)
        ctx = dict(full_context)

        if template_name == "post.html":
            ctx.update({"issue": mock_issue, "slug": "1-test", "html_body": "<p>Test</p>"})
        elif template_name in ["index.html", "tag.html"]:
            ctx.update({"issues": [mock_issue], "issue_slugs": {"1": "1-test"}, "tags": ["python"], "pagination": {"page": 1, "pages": 1, "has_prev": False, "has_next": False}})
        elif template_name == "tags.html":
            ctx.update({"tags": ["python"], "tag_items": [{"name": "python", "count": 1}]})
        elif template_name == "home.html":
            ctx.update({"issues": [mock_issue], "issue_slugs": {"1": "1-test"}})

        html = template.render(**ctx)
        assert isinstance(html, str), f"{template_name} failed"