from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from escaping.config import BuiltinThemeConfig, LocalThemeConfig, Settings
from escaping.models.blog_post import BlogPost, BlogTag
from escaping.models.content import AboutPage, ContentCompilationResult, Idea
from escaping.models.site import SiteModel
from escaping.projects import ProjectCompiler
from escaping.routes import RouteRegistry
from escaping.site_builder import SiteBuilder

_BUILD_START = datetime(2026, 2, 1, tzinfo=UTC)


def _settings(*, navigation_url: str = "/blog/", title: str = "Site") -> Settings:
    return Settings.model_validate(
        {
            "github": {"repo": "owner/site", "allowed_authors": ["owner"]},
            "site": {
                "title": title,
                "author": "Owner",
                "url": "https://example.com/",
                "description": "Description",
                "language": "en",
                "thesis": ["Question assumptions.", "Build useful tools."],
                "navigation": {"items": [{"name": "Blog", "url": navigation_url}]},
            },
            "profile": {
                "avatar": "/avatar.png",
                "tagline": "Analyst / tool builder",
                "bio": "Bio",
                "links": [{"name": "GitHub", "url": "https://github.com/owner"}],
            },
            "about": {"issue_number": 10},
            "paths": {"page_size": 2},
            "comments": {"theme": "github-light", "theme_mode": "auto"},
            "security": {"token_env": "TOKEN"},
        }
    )


def _blog(routes: RouteRegistry, number: int, *, naive: bool = False) -> BlogPost:
    published = datetime(2026, 1, number)
    if not naive:
        published = published.replace(tzinfo=UTC)
    tag_route = routes.tag("python")
    return BlogPost(
        issue_number=number,
        title=f"Post {number}",
        slug=f"post-{number}",
        description=f"Description {number}",
        created_date=f"2026-01-{number:02d}",
        published_at=published,
        updated_at=published,
        tags=(BlogTag("python", tag_route.canonical_path),),
        body_html="<p>Body.</p>",
        route=routes.blog_detail(f"post-{number}"),
    )


def _content(
    routes: RouteRegistry, blogs: tuple[BlogPost, ...] = ()
) -> ContentCompilationResult:
    idea = Idea(
        issue_number=2,
        title="Idea",
        description="Idea description",
        created_date="2026-01-02",
        published_at=datetime(2026, 1, 2, tzinfo=UTC),
        updated_at=datetime(2026, 1, 2, tzinfo=UTC),
        tags=(),
        body_html="<p>Idea.</p>",
        route=routes.idea(2),
    )
    about = AboutPage(
        issue_number=10,
        title="About",
        description="About description",
        body_html="<p>About.</p>",
        route=routes.about(),
    )
    return ContentCompilationResult(blogs=blogs, ideas=(idea,), about=about)


def _build(
    settings: Settings,
    routes: RouteRegistry,
    content: ContentCompilationResult,
) -> SiteModel:
    projects = ProjectCompiler().compile([], route=routes.projects())
    return SiteBuilder(settings, route_registry=routes).build(
        content, projects, build_start_time=_BUILD_START
    )


def test_site_builder_composes_metadata_routes_and_internal_page_models() -> None:
    settings = _settings()
    routes = RouteRegistry(str(settings.site.url))
    blogs = tuple(_blog(routes, number) for number in (2, 6, 1, 5, 3, 4))

    site = _build(settings, routes, _content(routes, blogs))

    assert not site.has_errors
    assert site.metadata.title == "Site"
    assert site.metadata.navigation[0].url == "/blog/"
    assert site.metadata.thesis == ("Question assumptions.", "Build useful tools.")
    assert site.metadata.profile.tagline == "Analyst / tool builder"
    assert site.metadata.profile.bio == "Bio"
    assert site.metadata.comments.repo == "owner/site"
    assert site.metadata.theme.name == "geoqiao.me"
    assert site.metadata.theme.asset_path == "/templates/geoqiao.me"

    assert site.home.route is routes.route("home")
    assert [post.issue_number for post in site.home.recent_posts] == [6, 5, 4, 3, 2]
    assert [post.description for post in site.home.recent_posts] == [
        "Description 6",
        "Description 5",
        "Description 4",
        "Description 3",
        "Description 2",
    ]
    assert [len(page.entries) for page in site.archives] == [2, 2, 2]
    assert site.archives[0].route is routes.route("blog")
    assert site.archives[0].next_route is site.archives[1].route
    assert site.archives[1].prev_route is site.archives[0].route

    assert site.ideas_page.route is routes.route("ideas")
    assert site.ideas[0].route is routes.route("idea-2")
    assert site.about is not None and site.about.route is routes.route("about")
    assert site.projects.route is routes.route("projects")
    assert site.tags.route is routes.route("tags")
    assert site.tags.tags[0].count == 6
    assert site.tag_archives[0].route is routes.route("tag-python")
    assert site.feed.route is routes.route("atom")
    assert [entry.title for entry in site.feed.entries] == [
        "Post 6",
        "Post 5",
        "Post 4",
        "Post 3",
        "Post 2",
        "Post 1",
    ]


def test_site_builder_has_intentional_empty_blog_models() -> None:
    settings = _settings()
    routes = RouteRegistry(str(settings.site.url))

    site = _build(settings, routes, _content(routes))

    assert not site.has_errors
    assert len(site.archives) == 1 and site.archives[0].entries == ()
    assert site.home.recent_posts == ()
    assert site.tags.tags == () and site.tag_archives == ()
    assert site.feed.entries == () and site.feed.updated == _BUILD_START


@pytest.mark.parametrize(
    ("theme", "expected_fields"),
    [
        (
            BuiltinThemeConfig(name="geoqiao.me"),
            {"site.thesis", "profile.tagline", "profile.bio"},
        ),
        (
            BuiltinThemeConfig(name="Escape1"),
            {"site.thesis", "profile.tagline"},
        ),
        (
            BuiltinThemeConfig(name="Escape2"),
            {"site.thesis", "profile.tagline"},
        ),
        (LocalThemeConfig(name="custom", path=Path("theme")), set()),
    ],
    ids=("geoqiao", "escape1", "escape2", "local"),
)
def test_site_builder_reports_only_known_unrendered_theme_fields(
    theme: BuiltinThemeConfig | LocalThemeConfig, expected_fields: set[str]
) -> None:
    settings = _settings().model_copy(update={"theme": theme})
    routes = RouteRegistry(str(settings.site.url))

    site = _build(settings, routes, _content(routes))

    warnings = {
        diagnostic.field
        for diagnostic in site.diagnostics
        if diagnostic.code == "THEME_FIELD_NOT_RENDERED"
    }
    assert warnings == expected_fields
    assert site.metadata.thesis == (
        "Question assumptions.",
        "Build useful tools.",
    )
    assert site.metadata.profile.tagline == "Analyst / tool builder"
    assert site.metadata.profile.bio == "Bio"


def test_site_builder_reports_navigation_and_atom_safety_errors() -> None:
    settings = _settings(navigation_url="/missing/", title="Bad\x01Title")
    routes = RouteRegistry(str(settings.site.url))
    naive = _blog(routes, 1, naive=True)

    site = _build(settings, routes, _content(routes, (naive,)))

    codes = {diagnostic.code for diagnostic in site.diagnostics}
    assert site.has_errors
    assert "ROUTE_COLLISION" in codes
    assert "ATOM_XML_INVALID_CHAR" in codes
    assert "ATOM_NAIVE_PUBLISHED_AT" in codes
    assert "ATOM_NAIVE_UPDATED_AT" in codes
