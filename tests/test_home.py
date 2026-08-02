"""Tests for the Home page builder, renderer, and templates (Ticket 06)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from github_blog.config import NavigationLink, ProfileLink, Settings
from github_blog.home_builder import HOME_POST_COUNT, HomeBuilder, write_home_page
from github_blog.models.blog_post import BlogPost, BlogTag
from github_blog.models.home_page import (
    HomeNavigationLink,
    HomePage,
    HomeProfile,
    HomeProfileLink,
    HomeRoute,
)
from github_blog.services.render_service import RenderService

PROJECT_ROOT = Path(__file__).parent.parent.absolute()


def _settings(
    *,
    theme: str = "Escape1",
    bio: str = "Test bio",
    avatar: str = "https://github.com/user.png",
    links: list[ProfileLink] | None = None,
    navigation: list[NavigationLink] | None = None,
    description: str = "Site description.",
) -> Settings:
    if links is None:
        links = [ProfileLink(name="GitHub", url="https://github.com/user")]
    if navigation is None:
        navigation = [NavigationLink(name="Blog", url="/blog/")]
    return Settings.model_validate(
        {
            "github": {"repo": "user/repo", "allowed_authors": ["user"]},
            "site": {
                "title": "Test Blog",
                "url": "https://example.com/",
                "author": "Author",
                "description": description,
                "language": "en",
                "navigation": {
                    "items": [{"name": n.name, "url": n.url} for n in navigation]
                },
            },
            "profile": {
                "avatar": avatar,
                "bio": bio,
                "links": [{"name": link.name, "url": link.url} for link in links],
            },
            "about": {"issue_number": 1},
            "paths": {"theme": theme},
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


class TestHomeBuilder:
    def test_five_limit_order_identity_profile_nav_strict_paths(self) -> None:
        """One builder scenario: 5-post limit, desc order with tie-break,
        identity/profile/navigation from Settings, strict detail/tag paths."""
        tie = datetime(2024, 1, 1, tzinfo=timezone.utc)
        tags = (BlogTag(name="python", path="/tags/python/"),)
        home = HomeBuilder(_settings()).build(
            [
                _post(5, datetime(2024, 5, 1, tzinfo=timezone.utc), tags=tags),
                _post(1, tie),
                _post(3, datetime(2024, 3, 1, tzinfo=timezone.utc)),
                _post(4, datetime(2024, 4, 1, tzinfo=timezone.utc)),
                _post(2, tie),
                _post(6, datetime(2024, 6, 1, tzinfo=timezone.utc)),
                _post(7, datetime(2024, 7, 1, tzinfo=timezone.utc)),
            ]
        )

        # Exactly 5 (limit), desc by published_at, tie-break by issue_number desc.
        assert len(home.recent_posts) == HOME_POST_COUNT == 5
        slugs = [e.detail_path.split("/")[2] for e in home.recent_posts]
        assert slugs == ["post-7", "post-6", "post-5", "post-4", "post-3"]

        # Identity from Settings.
        assert home.site_title == "Test Blog"
        assert home.site_author == "Author"
        assert home.site_description == "Site description."

        # Profile from Settings.
        assert home.profile.avatar == "https://github.com/user.png"
        assert home.profile.bio == "Test bio"
        assert home.profile.links[0].name == "GitHub"

        # Navigation from Settings.
        assert home.navigation[0].name == "Blog"
        assert home.navigation[0].url == "/blog/"

        # Route and canonical.
        assert home.route.canonical_path == "/"
        assert home.route.output_path == "index.html"
        assert home.canonical_url == "https://example.com/"

        # Strict detail path from BlogPost.canonical_path.
        assert home.recent_posts[2].detail_path == "/blog/post-5/"
        assert home.recent_posts[2].tags == tags


def test_home_builder_optional_and_empty() -> None:
    """Empty profile, description, navigation, and zero posts all build
    coherently."""
    settings = _settings(avatar="", bio="", links=[], navigation=[], description="")
    home = HomeBuilder(settings).build([])
    assert home.profile.avatar == ""
    assert home.profile.bio == ""
    assert home.profile.links == ()
    assert home.navigation == ()
    assert home.site_description == ""
    assert home.recent_posts == ()


@pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
def test_theme_sentinel_writer_homepage_is_sole_source(
    theme: str, tmp_path: Path
) -> None:
    """HomePage is the sole render source for identity/navigation/canonical.
    A sentinel HomePage distinct from Settings must override everything."""
    settings = _settings(
        theme=theme,
        description="SETTINGS_DESC_XYZ",
        navigation=[
            NavigationLink(name="SETTINGS_NAV_XYZ", url="/settings-nav-xyz/"),
        ],
    )
    home = HomePage(
        route=HomeRoute(canonical_path="/", output_path="index.html"),
        canonical_url="https://sentinel.example.com/",
        site_title="SENTINEL_TITLE_42",
        site_author="SENTINEL_AUTHOR_42",
        site_description="SENTINEL_DESC_42",
        profile=HomeProfile(
            avatar="https://sentinel.example.com/avatar.png",
            bio="SENTINEL_BIO_42",
            links=(
                HomeProfileLink(
                    name="SENTINEL_LINK_42",
                    url="https://sentinel.example.com/link",
                ),
            ),
        ),
        navigation=(
            HomeNavigationLink(name="SENTINEL_NAV_42", url="/sentinel-nav-42/"),
        ),
        recent_posts=(),
    )
    html = RenderService(settings).render_home_page(home)

    # HomePage values, not Settings values.
    assert "SENTINEL_TITLE_42" in html
    assert "Test Blog" not in html
    assert "SENTINEL_AUTHOR_42" in html
    assert "SENTINEL_DESC_42" in html
    assert "SETTINGS_DESC_XYZ" not in html
    assert "SENTINEL_NAV_42" in html
    assert "/sentinel-nav-42/" in html
    assert "SETTINGS_NAV_XYZ" not in html

    # Canonical/OG/Twitter URLs from HomePage origin.
    assert '<link rel="canonical" href="https://sentinel.example.com/"' in html
    assert '<meta property="og:url" content="https://sentinel.example.com/"' in html
    assert "https://example.com/" not in html

    # Empty state renders.
    assert "No blog posts yet." in html

    # Escape2 visible terminal identity from HomePage author.
    if theme == "Escape2":
        assert "SENTINEL_AUTHOR_42@escaping" in html

    # Strict writer tracer writes to index.html.
    written = write_home_page(home, RenderService(settings).render_home_page, tmp_path)
    assert written == (tmp_path / "index.html",)
    assert written[0].exists()
