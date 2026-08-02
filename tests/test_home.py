"""Tests for the Home page builder, renderer, and templates (Ticket 06).

Covers:
- HomeBuilder: exactly 5, fewer than 5, unsorted/tie, zero posts.
- HomeBuilder: identity/profile/navigation/CTA sourced from Settings.
- HomeBuilder: optional profile coherence.
- render_home_page: strict renderer consuming only HomePage.
- Legacy render_home adapter: sorts all issues, limits to 5, pre-computes
  legacy .html detail/tag hrefs.
- Strict tracer: writes Home to route.output_path (index.html).
- Template contract: both themes consume only HomePage, no issues/issue_slugs/
  labels/branding for Hero, no Markdown authority, intentional empty state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from github_blog.config import (
    NavigationLink,
    ProfileLink,
    Settings,
)
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


# ---------------------------------------------------------------------------
# Settings / post helpers
# ---------------------------------------------------------------------------


def _settings(
    *,
    theme: str = "Escape1",
    bio: str = "Test bio",
    avatar: str = "https://github.com/user.png",
    links: list[ProfileLink] | None = None,
    navigation: list[NavigationLink] | None = None,
    description: str = "Site description.",
    blog: str = "blog",
    tag: str = "tag",
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
            "paths": {"theme": theme, "blog": blog, "tag": tag},
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


# ---------------------------------------------------------------------------
# HomeBuilder: post count and ordering
# ---------------------------------------------------------------------------


class TestHomeBuilderPostCount:
    def test_exactly_five_when_more_than_five(self) -> None:
        builder = HomeBuilder(_settings())
        home = builder.build(_posts(7))
        assert len(home.recent_posts) == HOME_POST_COUNT
        assert len(home.recent_posts) == 5

    def test_fewer_than_five_shows_all(self) -> None:
        builder = HomeBuilder(_settings())
        home = builder.build(_posts(3))
        assert len(home.recent_posts) == 3

    def test_zero_posts_produces_empty_recent_posts(self) -> None:
        builder = HomeBuilder(_settings())
        home = builder.build([])
        assert home.recent_posts == ()

    def test_home_post_count_is_five(self) -> None:
        assert HOME_POST_COUNT == 5


class TestHomeBuilderOrdering:
    def test_sorts_by_published_at_descending(self) -> None:
        posts = [
            _post(1, datetime(2024, 1, 1, tzinfo=timezone.utc), title="Older"),
            _post(2, datetime(2024, 2, 1, tzinfo=timezone.utc), title="Newer"),
        ]
        home = HomeBuilder(_settings()).build(posts)
        assert [e.title for e in home.recent_posts] == ["Newer", "Older"]

    def test_tiebreak_by_issue_number_descending(self) -> None:
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        posts = [_post(1, ts), _post(3, ts), _post(2, ts)]
        home = HomeBuilder(_settings()).build(posts)
        assert [e.title for e in home.recent_posts] == [
            "Post 3",
            "Post 2",
            "Post 1",
        ]

    def test_unsorted_input_is_sorted(self) -> None:
        posts = [
            _post(5, datetime(2024, 5, 1, tzinfo=timezone.utc)),
            _post(1, datetime(2024, 1, 1, tzinfo=timezone.utc)),
            _post(3, datetime(2024, 3, 1, tzinfo=timezone.utc)),
            _post(4, datetime(2024, 4, 1, tzinfo=timezone.utc)),
            _post(2, datetime(2024, 2, 1, tzinfo=timezone.utc)),
            _post(6, datetime(2024, 6, 1, tzinfo=timezone.utc)),
        ]
        home = HomeBuilder(_settings()).build(posts)
        numbers = [
            int(e.detail_path.split("/")[2].split("-")[-1]) for e in home.recent_posts
        ]
        assert numbers == [6, 5, 4, 3, 2]


# ---------------------------------------------------------------------------
# HomeBuilder: identity / profile / navigation / CTA sources
# ---------------------------------------------------------------------------


class TestHomeBuilderSources:
    def test_site_identity_from_settings(self) -> None:
        settings = _settings(description="My site description.")
        home = HomeBuilder(settings).build([])
        assert home.site_title == "Test Blog"
        assert home.site_author == "Author"
        assert home.site_description == "My site description."

    def test_profile_from_settings(self) -> None:
        settings = _settings(
            avatar="https://github.com/user.png",
            bio="Short bio.",
            links=[ProfileLink(name="GitHub", url="https://github.com/user")],
        )
        home = HomeBuilder(settings).build([])
        assert home.profile.avatar == "https://github.com/user.png"
        assert home.profile.bio == "Short bio."
        assert len(home.profile.links) == 1
        assert home.profile.links[0].name == "GitHub"
        assert home.profile.links[0].url == "https://github.com/user"

    def test_navigation_from_settings(self) -> None:
        settings = _settings(
            navigation=[
                NavigationLink(name="Blog", url="/blog/"),
                NavigationLink(name="Tags", url="/tags/"),
            ]
        )
        home = HomeBuilder(settings).build([])
        assert len(home.navigation) == 2
        assert home.navigation[0].name == "Blog"
        assert home.navigation[0].url == "/blog/"
        assert home.navigation[1].name == "Tags"

    def test_route_is_fixed_root(self) -> None:
        home = HomeBuilder(_settings()).build([])
        assert home.route.canonical_path == "/"
        assert home.route.output_path == "index.html"

    def test_canonical_url_from_origin(self) -> None:
        home = HomeBuilder(_settings()).build([])
        assert home.canonical_url == "https://example.com/"

    def test_recent_post_detail_path_from_blogpost_canonical(self) -> None:
        post = _post(
            1,
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            slug="my-slug",
        )
        home = HomeBuilder(_settings()).build([post])
        assert home.recent_posts[0].detail_path == "/blog/my-slug/"

    def test_recent_post_tags_carry_strict_paths(self) -> None:
        tags = (BlogTag(name="python", path="/tags/python/"),)
        post = _post(
            1,
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            tags=tags,
        )
        home = HomeBuilder(_settings()).build([post])
        assert home.recent_posts[0].tags == tags


# ---------------------------------------------------------------------------
# HomeBuilder: optional profile coherence
# ---------------------------------------------------------------------------


class TestHomeBuilderOptionalProfile:
    def test_empty_profile_builds_successfully(self) -> None:
        settings = _settings(avatar="", bio="", links=[])
        home = HomeBuilder(settings).build([])
        assert home.profile.avatar == ""
        assert home.profile.bio == ""
        assert home.profile.links == ()

    def test_empty_description_builds_successfully(self) -> None:
        settings = _settings(description="")
        home = HomeBuilder(settings).build([])
        assert home.site_description == ""

    def test_empty_navigation_builds_successfully(self) -> None:
        settings = _settings(navigation=[])
        home = HomeBuilder(settings).build([])
        assert home.navigation == ()


# ---------------------------------------------------------------------------
# HomeBuilder: model immutability and no PyGithub leakage
# ---------------------------------------------------------------------------


class TestHomeBuilderModelContract:
    def test_home_page_is_immutable(self) -> None:
        import dataclasses

        home = HomeBuilder(_settings()).build([])
        with pytest.raises(dataclasses.FrozenInstanceError):
            home.site_title = "changed"  # type: ignore

    def test_home_page_does_not_expose_pygithub_objects(self) -> None:
        home = HomeBuilder(_settings()).build([])
        for leaked in ("issues", "issue_slugs", "labels", "issue", "branding"):
            assert not hasattr(home, leaked)
        for entry in home.recent_posts:
            for leaked in ("issue", "labels", "issue_slugs"):
                assert not hasattr(entry, leaked)


# ---------------------------------------------------------------------------
# Strict renderer: render_home_page
# ---------------------------------------------------------------------------


class TestRenderHomePage:
    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_renders_recent_post_titles(self, theme: str) -> None:
        home = HomeBuilder(_settings(theme=theme)).build(_posts(3))
        html = _render(theme).render_home_page(home)
        assert "Post 1" in html
        assert "Post 2" in html
        assert "Post 3" in html

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_renders_pre_computed_detail_links(self, theme: str) -> None:
        home = HomeBuilder(_settings(theme=theme)).build(_posts(2))
        html = _render(theme).render_home_page(home)
        assert 'href="/blog/post-1/"' in html
        assert 'href="/blog/post-2/"' in html

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_renders_pre_computed_tag_links(self, theme: str) -> None:
        tags = (BlogTag(name="python", path="/tags/python/"),)
        post = _post(
            1,
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            tags=tags,
        )
        home = HomeBuilder(_settings(theme=theme)).build([post])
        html = _render(theme).render_home_page(home)
        assert 'href="/tags/python/"' in html

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_renders_navigation_actions(self, theme: str) -> None:
        """Hero shows navigation actions sourced from home.navigation."""
        settings = _settings(
            theme=theme,
            navigation=[
                NavigationLink(name="Blog", url="/blog/"),
                NavigationLink(name="Tags", url="/tag/"),
            ],
        )
        home = HomeBuilder(settings).build([])
        html = _render(theme).render_home_page(home)
        assert "Blog" in html
        assert 'href="/blog/"' in html
        assert "Tags" in html
        assert 'href="/tag/"' in html

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_renders_avatar_when_present(self, theme: str) -> None:
        """Hero renders profile avatar with alt=site_author when non-empty."""
        settings = _settings(
            theme=theme,
            avatar="https://github.com/user.png",
        )
        home = HomeBuilder(settings).build([])
        html = _render(theme).render_home_page(home)
        assert "https://github.com/user.png" in html
        assert 'alt="Author"' in html

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_does_not_render_avatar_when_absent(self, theme: str) -> None:
        """Hero omits avatar img when avatar is empty."""
        settings = _settings(theme=theme, avatar="")
        home = HomeBuilder(settings).build([])
        html = _render(theme).render_home_page(home)
        assert "<img" not in html

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_renders_site_title_as_heading(self, theme: str) -> None:
        """Hero shows site_title as a heading."""
        settings = _settings(theme=theme)
        home = HomeBuilder(settings).build([])
        html = _render(theme).render_home_page(home)
        assert "<h1" in html

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_no_hardcoded_cta_when_navigation_empty(self, theme: str) -> None:
        """No hardcoded 'View all posts' CTA when navigation is empty."""
        settings = _settings(theme=theme, navigation=[])
        home = HomeBuilder(settings).build([])
        html = _render(theme).render_home_page(home)
        assert "View all posts" not in html
        assert 'href="/blog/"' not in html

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_renders_canonical_link(self, theme: str) -> None:
        home = HomeBuilder(_settings(theme=theme)).build([])
        html = _render(theme).render_home_page(home)
        assert 'href="https://example.com/"' in html
        assert "canonical" in html.lower()

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_renders_empty_state_for_zero_posts(self, theme: str) -> None:
        home = HomeBuilder(_settings(theme=theme)).build([])
        html = _render(theme).render_home_page(home)
        assert 'class="empty-state"' in html
        assert "No blog posts yet." in html

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_renders_profile_when_present(self, theme: str) -> None:
        settings = _settings(
            theme=theme,
            avatar="https://github.com/user.png",
            bio="Short bio.",
            links=[ProfileLink(name="GitHub", url="https://github.com/user")],
        )
        home = HomeBuilder(settings).build([])
        html = _render(theme).render_home_page(home)
        assert "Short bio." in html
        assert "https://github.com/user" in html
        assert "https://github.com/user.png" in html
        assert 'alt="Author"' in html

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_coherent_when_profile_absent(self, theme: str) -> None:
        settings = _settings(theme=theme, avatar="", bio="", links=[])
        home = HomeBuilder(settings).build([])
        html = _render(theme).render_home_page(home)
        # Page still renders with navigation actions and empty state
        assert 'href="/blog/"' in html
        assert 'class="empty-state"' in html

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_coherent_when_all_empty(self, theme: str) -> None:
        """Profile, navigation, and posts all empty - page still coherent."""
        home = HomePage(
            route=HomeRoute(canonical_path="/", output_path="index.html"),
            canonical_url="https://example.com/",
            site_title="",
            site_author="",
            site_description="",
            profile=HomeProfile(avatar="", bio="", links=()),
            navigation=(),
            recent_posts=(),
        )
        html = _render(theme).render_home_page(home)
        assert "No blog posts yet." in html
        assert "View all posts" not in html

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_coherent_when_description_empty(self, theme: str) -> None:
        settings = _settings(theme=theme, description="")
        home = HomeBuilder(settings).build(_posts(1))
        html = _render(theme).render_home_page(home)
        assert "Post 1" in html


# ---------------------------------------------------------------------------
# HomePage as sole render source for Home identity/navigation
# ---------------------------------------------------------------------------


class TestHomePageIsSoleRenderSource:
    """HomePage must be the sole render source for Home identity/navigation.

    render_home_page() must not bypass HomePage by reading title/author/
    description/navigation from Settings common context.
    """

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_home_uses_homepage_sentinel_not_settings(self, theme: str) -> None:
        """Construct HomePage sentinel distinct from RenderService settings."""
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

        # Header/logo/<title> uses home.site_title, not settings.site.title
        assert "SENTINEL_TITLE_42" in html
        assert "Test Blog" not in html

        # Footer uses home.site_author, not settings.site.author
        assert "SENTINEL_AUTHOR_42" in html
        assert "&copy; Author" not in html

        # Meta description uses home.site_description, not settings.site.description
        assert "SENTINEL_DESC_42" in html
        assert "SETTINGS_DESC_XYZ" not in html

        # Header nav + Hero actions use home.navigation, not settings navigation
        assert "SENTINEL_NAV_42" in html
        assert "/sentinel-nav-42/" in html
        assert "SETTINGS_NAV_XYZ" not in html
        assert "/settings-nav-xyz/" not in html

        # Canonical, Open Graph, and Twitter URL metadata use HomePage origin.
        assert '<link rel="canonical" href="https://sentinel.example.com/"' in html
        assert '<meta property="og:url" content="https://sentinel.example.com/"' in html
        assert (
            '<meta name="twitter:url" content="https://sentinel.example.com/"' in html
        )
        assert "https://example.com/" not in html

        # Escape2's visible terminal identity also comes from HomePage author.
        if theme == "Escape2":
            assert "SENTINEL_AUTHOR_42@escaping" in html
            assert "user@escaping" not in html


# ---------------------------------------------------------------------------
# Strict tracer: write_home_page
# ---------------------------------------------------------------------------


class TestStrictHomeTracer:
    def test_writes_to_index_html(self, tmp_path: Path) -> None:
        home = HomeBuilder(_settings()).build(_posts(3))
        written = write_home_page(home, _render().render_home_page, tmp_path)
        assert written == (tmp_path / "index.html",)
        assert written[0].exists()
        content = written[0].read_text(encoding="utf-8")
        assert "Post 1" in content
        assert 'href="/blog/post-1/"' in content

    def test_writes_zero_post_home(self, tmp_path: Path) -> None:
        home = HomeBuilder(_settings()).build([])
        written = write_home_page(home, _render().render_home_page, tmp_path)
        assert written[0].exists()
        content = written[0].read_text(encoding="utf-8")
        assert "No blog posts yet." in content
        assert 'href="/blog/"' in content


# ---------------------------------------------------------------------------
# Legacy render_home adapter
# ---------------------------------------------------------------------------


def _legacy_issue(
    number: int,
    *,
    title: str | None = None,
    labels: list[str] | None = None,
    created_at: datetime | None = None,
) -> Any:  # noqa: ANN401
    issue = MagicMock()
    issue.number = number
    issue.title = title or f"Post {number}"
    issue.labels = []
    for label_name in labels or []:
        label = MagicMock()
        label.name = label_name
        issue.labels.append(label)
    issue.created_at = created_at or datetime(2024, 1, number, tzinfo=timezone.utc)
    return issue


class TestLegacyHomeAdapter:
    def test_sorts_all_issues_and_limits_to_five(self) -> None:
        """Adapter must sort ALL issues, not rely on pre-sliced input."""
        issues = [
            _legacy_issue(i, created_at=datetime(2024, 1, i, tzinfo=timezone.utc))
            for i in range(1, 8)
        ]
        issue_slugs = {str(i): f"{i}-test" for i in range(1, 8)}
        html = _render().render_home(issues, issue_slugs)
        # Only the 5 newest (issues 7,6,5,4,3) should appear
        for i in [7, 6, 5, 4, 3]:
            assert f"Post {i}" in html
        # Issues 1 and 2 should NOT appear
        assert "Post 1" not in html
        assert "Post 2" not in html

    def test_unsorted_input_sorted_by_adapter(self) -> None:
        """Even if input is unsorted, adapter sorts correctly."""
        issues = [
            _legacy_issue(1, created_at=datetime(2024, 1, 1, tzinfo=timezone.utc)),
            _legacy_issue(3, created_at=datetime(2024, 3, 1, tzinfo=timezone.utc)),
            _legacy_issue(2, created_at=datetime(2024, 2, 1, tzinfo=timezone.utc)),
        ]
        issue_slugs = {"1": "1-test", "2": "2-test", "3": "3-test"}
        html = _render().render_home(issues, issue_slugs)
        # Post 3 should appear before Post 2 before Post 1
        pos3 = html.index("Post 3")
        pos2 = html.index("Post 2")
        pos1 = html.index("Post 1")
        assert pos3 < pos2 < pos1

    def test_tiebreak_by_issue_number_descending(self) -> None:
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        issues = [
            _legacy_issue(1, created_at=ts),
            _legacy_issue(3, created_at=ts),
            _legacy_issue(2, created_at=ts),
        ]
        issue_slugs = {"1": "1-test", "2": "2-test", "3": "3-test"}
        html = _render().render_home(issues, issue_slugs)
        pos3 = html.index("Post 3")
        pos2 = html.index("Post 2")
        pos1 = html.index("Post 1")
        assert pos3 < pos2 < pos1

    def test_legacy_detail_href_uses_html_extension(self) -> None:
        issues = [_legacy_issue(1, title="Legacy Post")]
        issue_slugs = {"1": "1-legacy-post"}
        html = _render().render_home(issues, issue_slugs)
        assert 'href="/blog/1-legacy-post.html"' in html
        # Strict path must NOT appear in legacy output
        assert "/blog/1-legacy-post/" not in html

    def test_legacy_tag_href_uses_html_extension(self) -> None:
        issues = [_legacy_issue(1, labels=["python"])]
        issue_slugs = {"1": "1-test"}
        html = _render().render_home(issues, issue_slugs)
        assert 'href="/tag/python.html"' in html
        assert "/tags/python/" not in html

    def test_legacy_zero_posts_shows_empty_state(self) -> None:
        html = _render().render_home([], {})
        assert 'class="empty-state"' in html
        assert "No blog posts yet." in html

    def test_legacy_fewer_than_five_shows_all(self) -> None:
        issues = [_legacy_issue(i) for i in range(1, 4)]
        issue_slugs = {str(i): f"{i}-test" for i in range(1, 4)}
        html = _render().render_home(issues, issue_slugs)
        for i in [1, 2, 3]:
            assert f"Post {i}" in html

    def test_legacy_navigation_from_settings(self) -> None:
        """Legacy adapter must construct navigation from settings, not empty."""
        settings = _settings(
            navigation=[
                NavigationLink(name="Tags", url="/tag/"),
                NavigationLink(name="About", url="/about.html"),
            ]
        )
        render = RenderService(settings)
        issues = [_legacy_issue(1)]
        issue_slugs = {"1": "1-test"}
        html = render.render_home(issues, issue_slugs)
        # Navigation from settings appears in header nav and Hero actions
        assert "Tags" in html
        assert 'href="/tag/"' in html
        assert "About" in html
        assert 'href="/about.html"' in html

    def test_legacy_renders_canonical_link(self) -> None:
        html = _render().render_home([], {})
        assert 'href="https://example.com/"' in html


# ---------------------------------------------------------------------------
# Template contract: forbidden old inputs, no Markdown authority
# ---------------------------------------------------------------------------


class TestTemplateContract:
    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_template_does_not_access_issues_or_slugs(self, theme: str) -> None:
        template = (PROJECT_ROOT / "templates" / theme / "home.html").read_text(
            encoding="utf-8"
        )
        for forbidden in (
            "issues",
            "issue_slugs",
            "issue.",
            "labels",
            "issue.number",
        ):
            assert forbidden not in template, (
                f"home.html ({theme}) must not reference {forbidden!r}"
            )

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_template_does_not_use_branding_for_hero(self, theme: str) -> None:
        template = (PROJECT_ROOT / "templates" / theme / "home.html").read_text(
            encoding="utf-8"
        )
        assert "branding" not in template, (
            f"home.html ({theme}) must not access branding for Hero"
        )

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_template_does_not_concatenate_urls(self, theme: str) -> None:
        template = (PROJECT_ROOT / "templates" / theme / "home.html").read_text(
            encoding="utf-8"
        )
        for forbidden in (
            "/blog/{{",
            "/tag/{{",
            "/blog/page/{{",
        ):
            assert forbidden not in template

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_template_uses_home_page_model(self, theme: str) -> None:
        template = (PROJECT_ROOT / "templates" / theme / "home.html").read_text(
            encoding="utf-8"
        )
        assert "home_page" in template
        assert "home_page.recent_posts" in template
        assert "home_page.profile.avatar" in template
        assert "home_page.navigation" in template
        assert "home_page.site_title" in template

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_template_does_not_bypass_homepage_for_identity(self, theme: str) -> None:
        """Home content block must use home_page.* not Settings-sourced vars."""
        template = (PROJECT_ROOT / "templates" / theme / "home.html").read_text(
            encoding="utf-8"
        )
        for forbidden in (
            "blog_title",
            "meta_description",
            "author_name",
            "navigation.items",
            "navigation_items",
            "about_avatar",
            "about_bio",
            "about_links",
        ):
            assert forbidden not in template, (
                f"home.html ({theme}) must not reference {forbidden!r}"
            )

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_template_uses_pre_computed_entry_paths(self, theme: str) -> None:
        template = (PROJECT_ROOT / "templates" / theme / "home.html").read_text(
            encoding="utf-8"
        )
        assert "post.detail_path" in template or "entry.detail_path" in template

    @pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
    def test_template_has_empty_state(self, theme: str) -> None:
        template = (PROJECT_ROOT / "templates" / theme / "home.html").read_text(
            encoding="utf-8"
        )
        assert "empty-state" in template
        assert "No blog posts yet." in template


# ---------------------------------------------------------------------------
# Two-theme equivalence
# ---------------------------------------------------------------------------


class TestTwoThemeEquivalence:
    def test_both_themes_render_same_post_data(self) -> None:
        home = HomeBuilder(_settings()).build(_posts(3))
        html1 = _render("Escape1").render_home_page(home)
        html2 = _render("Escape2").render_home_page(home)
        for title in ["Post 1", "Post 2", "Post 3"]:
            assert title in html1
            assert title in html2
        assert 'href="/blog/post-1/"' in html1
        assert 'href="/blog/post-1/"' in html2

    def test_both_themes_render_same_empty_state(self) -> None:
        home = HomeBuilder(_settings()).build([])
        html1 = _render("Escape1").render_home_page(home)
        html2 = _render("Escape2").render_home_page(home)
        assert "No blog posts yet." in html1
        assert "No blog posts yet." in html2
        assert 'href="/blog/"' in html1
        assert 'href="/blog/"' in html2

    def test_both_themes_render_same_profile(self) -> None:
        settings = _settings(
            avatar="https://github.com/user.png",
            bio="Shared bio.",
        )
        home = HomeBuilder(settings).build([])
        html1 = _render("Escape1").render_home_page(home)
        html2 = _render("Escape2").render_home_page(home)
        assert "Shared bio." in html1
        assert "Shared bio." in html2
        assert "https://github.com/user.png" in html1
        assert "https://github.com/user.png" in html2
        assert 'alt="Author"' in html1
        assert 'alt="Author"' in html2
