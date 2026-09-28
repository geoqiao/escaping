from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import pytest

from escaping.config import ExtraPageConfig, Settings
from escaping.models.blog_post import BlogPost, BlogTag
from escaping.models.content import AboutPage, ContentCompilationResult, Idea
from escaping.models.site import SiteModel
from escaping.projects import ProjectCompiler
from escaping.routes import RouteRegistry
from escaping.site_builder import SiteBuilder

_BUILD_START = datetime(2026, 2, 1, tzinfo=UTC)


def _settings(**overrides: object) -> Settings:
    data: dict[str, Any] = {
        "github": {"repo": "owner/site", "allowed_authors": ["owner"]},
        "site": {
            "title": "Site",
            "author": "Owner",
            "url": "https://example.com/",
            "description": "Description",
            "navigation": {"items": [{"name": "Blog", "url": "/blog/"}]},
        },
        "profile": {"avatar": "/avatar.png", "bio": "Bio"},
        "paths": {"page_size": 2},
        "comments": {"enabled": True},
        "seo": {"social_image": "/assets/images/og.png"},
    }
    for key, value in overrides.items():
        section, _, name = key.partition("__")
        if name:
            data[section] = {**data.get(section, {}), name: value}
        else:
            data[section] = value
    return Settings.model_validate(data)


def _extra(path: str, template: str, for_each: str | None = None) -> ExtraPageConfig:
    return ExtraPageConfig.model_validate(
        {"path": path, "template": template, "for_each": for_each}
    )


def _blog(
    routes: RouteRegistry,
    number: int,
    *,
    tags: Sequence[tuple[str, str]] = (("Python", "python"),),
    naive: bool = False,
) -> BlogPost:
    published = datetime(2026, 1, number, tzinfo=None if naive else UTC)
    return BlogPost(
        issue_number=number,
        title=f"Post {number}",
        slug=f"post-{number}",
        description=f"Description {number}",
        created_date=f"2026-01-{number:02d}",
        published_at=published,
        updated_at=published,
        tags=tuple(
            BlogTag(name, key, routes.tag(key) if routes.sections.tags else None)
            for name, key in tags
        ),
        body_html="<p>Body.</p>",
        route=routes.blog_detail(f"post-{number}"),
    )


def _content(
    routes: RouteRegistry,
    blogs: tuple[BlogPost, ...] = (),
    *,
    about: bool = True,
    skipped: tuple[int, ...] = (),
) -> ContentCompilationResult:
    """One Idea and an About Issue, for the sections that are on."""
    date = datetime(2026, 1, 2, tzinfo=UTC)
    ideas = (
        (
            Idea(
                issue_number=20,
                title="Idea",
                description="Idea description",
                created_date="2026-01-02",
                published_at=date,
                updated_at=date,
                tags=(),
                body_html="<p>Idea.</p>",
                route=routes.idea(20),
            ),
        )
        if routes.sections.ideas
        else ()
    )
    page = (
        AboutPage(
            issue_number=10,
            title="About",
            description="About description",
            body_html="<p>About.</p>",
            route=routes.about(),
        )
        if about and routes.sections.about
        else None
    )
    return ContentCompilationResult(
        blogs=blogs, ideas=ideas, about=page, skipped=skipped
    )


def _build(
    settings: Settings,
    routes: RouteRegistry,
    content: ContentCompilationResult,
    pages: Sequence[ExtraPageConfig] = (),
) -> SiteModel:
    projects = ProjectCompiler().compile(settings.projects)
    return SiteBuilder(settings, route_registry=routes).build(
        content, projects, pages=pages, build_start_time=_BUILD_START
    )


def test_site_builder_composes_the_site_from_registered_routes() -> None:
    settings = _settings()
    routes = RouteRegistry(str(settings.site.url))
    blogs = tuple(_blog(routes, number) for number in (2, 6, 1, 5, 3, 4))

    site = _build(settings, routes, _content(routes, blogs, skipped=(7,)))

    assert not site.has_errors, site.diagnostics
    assert site.skipped_issues == (7,)
    assert [[post.issue_number for post in page.posts] for page in site.archives] == [
        [6, 5],
        [4, 3],
        [2, 1],
    ]
    assert site.archives[0].route is routes.route("blog")
    assert site.archives[0].next_route is site.archives[1].route
    assert site.archives[2].prev_route is site.archives[1].route
    assert site.archives[2].next_route is None
    assert [(tag.name, tag.count) for tag in site.tags] == [("Python", 6)]
    assert site.tags[0].route is routes.route("tag-python")
    assert [entry.title for entry in site.feed.entries][:2] == ["Post 6", "Post 5"]
    assert site.about is not None and not site.about.is_profile
    assert site.about.route is routes.route("about")
    metadata = site.metadata
    assert metadata.comments.enabled and metadata.comments.repo == "owner/site"
    assert metadata.seo.social_image == "https://example.com/assets/images/og.png"
    assert [(link.name, link.url) for link in metadata.navigation] == [
        ("Blog", "/blog/")
    ]

    empty = _build(settings, RouteRegistry("https://example.com/"), _content(routes))
    assert len(empty.archives) == 1 and empty.archives[0].posts == ()
    assert empty.tags == () and empty.feed.updated == _BUILD_START


def test_tags_group_by_key_and_take_the_newest_spelling() -> None:
    settings = _settings()
    routes = RouteRegistry(str(settings.site.url))
    blogs = (
        _blog(routes, 1, tags=(("python", "python"), ("示例 标签", "示例-标签"))),
        _blog(routes, 3, tags=(("Python", "python"),)),
        _blog(routes, 2, tags=(("PYTHON", "python"),)),
    )
    site = _build(settings, routes, _content(routes, blogs))
    assert [(tag.name, tag.key) for tag in site.tags] == [
        ("Python", "python"),
        ("示例 标签", "示例-标签"),
    ]
    assert [post.issue_number for post in site.tags[0].posts] == [3, 2, 1]
    assert site.tags[1].canonical_path == "/tags/%E7%A4%BA%E4%BE%8B-%E6%A0%87%E7%AD%BE/"


def test_profile_about_stands_in_when_there_is_no_about_issue() -> None:
    for bio, expected in (("Bio", "Bio"), ("", "Description")):
        settings = _settings(profile__bio=bio)
        routes = RouteRegistry(str(settings.site.url))
        site = _build(settings, routes, _content(routes, about=False))
        assert not site.has_errors
        assert site.about is not None and site.about.is_profile
        assert (site.about.title, site.about.description) == ("Owner", expected)
        assert site.about.route is routes.route("about")


def test_extra_pages_get_routes_and_projects_link_their_first_detail_page() -> None:
    settings = _settings(
        projects=[{"repository": "owner/alpha"}, {"repository": "owner/beta"}],
        site__navigation={"items": [{"name": "Now", "url": "/now/"}]},
    )
    routes = RouteRegistry(str(settings.site.url))
    pages = (
        _extra("/now/", "now.html"),
        _extra("/work/{slug}/", "work.html", "projects"),
        _extra("/code/{slug}/", "code/{slug}.html", "projects"),
    )

    site = _build(settings, routes, _content(routes), pages)

    assert not site.has_errors, site.diagnostics
    assert [
        (page.route.output_path, page.template, page.project and page.project.slug)
        for page in site.extra_pages
    ] == [
        ("now/index.html", "now.html", None),
        ("work/alpha/index.html", "work.html", "alpha"),
        ("work/beta/index.html", "work.html", "beta"),
        ("code/alpha/index.html", "code/alpha.html", "alpha"),
        ("code/beta/index.html", "code/beta.html", "beta"),
    ]
    assert [project.page for project in site.projects] == [
        routes.route("page-/work/alpha/"),
        routes.route("page-/work/beta/"),
    ]
    assert site.extra_pages[4].project == site.projects[1]
    assert site.metadata.navigation[0].url == "/now/"
    assert routes.route("page-/now/") in routes.sitemap_routes()


@pytest.mark.parametrize(
    "pages",
    [
        # A project named "blog" would take the Blog archive's address.
        (_extra("/{slug}/", "project.html", "projects"),),
        # A fixed page at a path that a project detail page also uses.
        (
            _extra("/work/{slug}/", "work.html", "projects"),
            _extra("/work/escaping/", "special.html"),
        ),
    ],
)
def test_extra_pages_cannot_share_an_address(
    pages: tuple[ExtraPageConfig, ...],
) -> None:
    settings = _settings(
        projects=[{"repository": "owner/blog"}, {"repository": "owner/escaping"}]
    )
    routes = RouteRegistry(str(settings.site.url))

    site = _build(settings, routes, _content(routes), pages)

    assert site.has_errors
    assert [(d.code, d.field) for d in site.diagnostics if d.severity == "error"] == [
        ("ROUTE_COLLISION", "pages.extra")
    ]


@pytest.mark.parametrize("url", ["/missing/", "/Blog/", "/now/"])
def test_navigation_must_point_at_pages_of_the_site(url: str) -> None:
    settings = _settings(
        site__navigation={
            "items": [
                {"name": "Page", "url": url},
                {"name": "Elsewhere", "url": "https://example.org/"},
            ]
        }
    )
    routes = RouteRegistry(str(settings.site.url))
    site = _build(settings, routes, _content(routes))
    assert [(d.code, d.field) for d in site.diagnostics] == [
        ("ROUTE_COLLISION", "site.navigation")
    ]

    defaults = _settings(site__navigation={})
    routes = RouteRegistry(str(defaults.site.url))
    site = _build(defaults, routes, _content(routes))
    assert not site.diagnostics
    assert [link.url for link in site.metadata.navigation] == [
        "/",
        "/blog/",
        "/projects/",
        "/tags/",
        "/about/",
        "/atom.xml",
    ]


def test_invalid_feed_text_and_naive_timestamps_stop_the_build() -> None:
    settings = _settings(site__title="Bad\x01Title")
    routes = RouteRegistry(str(settings.site.url))
    site = _build(settings, routes, _content(routes, (_blog(routes, 1, naive=True),)))
    codes = {d.code for d in site.diagnostics if d.severity == "error"}
    assert site.has_errors
    assert {
        "ATOM_XML_INVALID_CHAR",
        "ATOM_NAIVE_PUBLISHED_AT",
        "ATOM_NAIVE_UPDATED_AT",
    } <= codes


def test_profile_about_body_is_the_escaped_bio() -> None:
    settings = _settings(profile__bio="Tea & <code>")
    routes = RouteRegistry(str(settings.site.url))
    site = _build(settings, routes, _content(routes, about=False))
    assert site.about is not None
    assert site.about.body_html == "<p>Tea &amp; &lt;code&gt;</p>"
    assert site.about.issue_number is None and site.about.tags == ()


def test_sections_can_move_or_be_turned_off() -> None:
    settings = _settings(
        pages={"blog": "/posts/", "ideas": False, "tags": False, "about": "/me/"},
        site__navigation={},
    )
    routes = RouteRegistry(str(settings.site.url), settings.pages.sections())
    blogs = tuple(_blog(routes, number) for number in (1, 2, 3))

    site = _build(settings, routes, _content(routes, blogs))

    assert not site.has_errors, site.diagnostics
    assert sorted(route.canonical_path for route in routes.sitemap_routes()) == [
        "/",
        "/me/",
        "/posts/",
        "/posts/page/2/",
        "/posts/post-1/",
        "/posts/post-2/",
        "/posts/post-3/",
        "/projects/",
    ]
    assert routes.get("ideas") is None and routes.get("tags") is None
    assert site.tags == () and site.ideas == ()
    assert [tag.path for tag in site.blogs[0].tags] == [None]
    assert site.about is not None and site.about.canonical_path == "/me/"
    assert [(link.name, link.url) for link in site.metadata.navigation] == [
        ("Home", "/"),
        ("Blog", "/posts/"),
        ("Projects", "/projects/"),
        ("About", "/me/"),
        ("RSS", "/atom.xml"),
    ]


def test_navigation_to_a_page_that_is_off_says_so() -> None:
    settings = _settings(
        pages={"tags": False},
        site__navigation={"items": [{"name": "Tags", "url": "/tags/"}]},
    )
    routes = RouteRegistry(str(settings.site.url), settings.pages.sections())
    site = _build(settings, routes, _content(routes))
    assert [d.message for d in site.diagnostics] == [
        "navigation item Tags points to /tags/, which is not a page of this site "
        "(pages.tags is false)"
    ]
