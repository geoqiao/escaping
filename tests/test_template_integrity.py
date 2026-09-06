from __future__ import annotations

import json
import re
import struct
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

import pytest
from jinja2 import ChoiceLoader, DictLoader

from escaping.config import Settings
from escaping.content_compiler import ContentCompiler
from escaping.models.blog_post import BlogPost, BlogTag
from escaping.models.content import ContentCompilationResult
from escaping.models.issue_snapshot import IssueSnapshot
from escaping.projects import ProjectCompiler
from escaping.routes import RouteRegistry
from escaping.services.render_service import RenderService
from escaping.site_builder import SiteBuilder
from escaping.theme import ThemeLoader

_ROOT = Path(__file__).parent.parent.absolute()
_MERMAID_VERSION = "11.16.1"
_MERMAID_ASSET = f"static/vendor/mermaid-{_MERMAID_VERSION}/mermaid.min.js"
_ADJACENT_POSTS: tuple[tuple[int, str, str, datetime, str], ...] = (
    (4, "Tie low", "tie-low", datetime(2026, 1, 2, tzinfo=UTC), "focus"),
    (1, "Oldest post", "oldest", datetime(2026, 1, 1, tzinfo=UTC), "focus"),
    (11, "Newest post", "newest", datetime(2026, 1, 3, tzinfo=UTC), "focus"),
    (12, "Older post", "older", datetime(2026, 1, 1, tzinfo=UTC), "other"),
    (7, "Tie <high> & safe", "tie-high", datetime(2026, 1, 2, tzinfo=UTC), "other"),
)


def _settings(
    theme: str,
    *,
    language: str = "en",
    title: str = "Site",
    author: str = "geoqiao",
    avatar: str = "",
    thesis: list[str] | None = None,
    tagline: str = "",
    bio: str = "",
    projects: list[dict[str, object]] | None = None,
    page_size: int | None = None,
    comments_enabled: bool = True,
) -> Settings:
    site: dict[str, object] = {
        "title": title,
        "author": author,
        "url": "https://geoqiao.me/",
        "language": language,
        "navigation": {"items": [{"name": "Blog", "url": "/blog/"}]},
    }
    if thesis is not None:
        site["thesis"] = thesis
    data: dict[str, object] = {
        "github": {"repo": "geoqiao/site", "allowed_authors": ["geoqiao"]},
        "site": site,
        "profile": {"avatar": avatar, "tagline": tagline, "bio": bio},
        "about": {"issue_number": 10},
        "theme": {"source": "builtin", "name": theme},
        "security": {"token_env": "TOKEN"},
        "comments": {"enabled": comments_enabled},
    }
    if projects is not None:
        data["projects"] = projects
    if page_size is not None:
        data["paths"] = {"page_size": page_size}
    return Settings.model_validate(data)


def _snap(
    number: int, kind: str, metadata: str, *, labels: tuple[str, ...] = ()
) -> IssueSnapshot:
    now = datetime(2026, 1, number, tzinfo=UTC)
    return IssueSnapshot(
        number,
        kind.title(),
        "geoqiao",
        f"---\n{metadata}\n---\n\nBody **content**.",
        (f"type:{kind}", "published", *labels),
        now,
        now,
        False,
    )


def _render_theme(
    theme: str,
    *,
    language: str = "en",
    title: str = "Site",
    author: str = "geoqiao",
    avatar: str = "",
    thesis: list[str] | None = None,
    tagline: str = "",
    bio: str = "",
    projects: list[dict[str, object]] | None = None,
    comments_enabled: bool = True,
) -> dict[str, str]:
    settings = _settings(
        theme,
        language=language,
        title=title,
        author=author,
        avatar=avatar,
        thesis=thesis,
        tagline=tagline,
        bio=bio,
        projects=projects,
        comments_enabled=comments_enabled,
    )
    routes = RouteRegistry(str(settings.site.url))
    content = ContentCompiler(settings, route_registry=routes).compile(
        [
            _snap(
                1,
                "blog",
                'slug: post\ndescription: Post.\ncreated_date: "2026-01-01"',
                labels=("tag:python",),
            ),
            _snap(
                2,
                "idea",
                'description: Idea.\ncreated_date: "2026-01-02"',
                labels=("tag:idea-only", "tag:python"),
            ),
            _snap(10, "about", 'description: About.\ncreated_date: "2026-01-03"'),
        ]
    )
    site = SiteBuilder(settings, route_registry=routes).build(
        content,
        ProjectCompiler().compile(settings.projects, route=routes.projects()),
        build_start_time=datetime(2026, 1, 20, tzinfo=UTC),
    )
    assert not site.has_errors
    loaded_theme = ThemeLoader(_ROOT).load(settings.theme)
    return RenderService(loaded_theme).render_site(site)


def _local_blog(
    routes: RouteRegistry,
    issue_number: int,
    title: str,
    slug: str,
    published_at: datetime,
    tag_name: str,
) -> BlogPost:
    tag_route = routes.tag(tag_name)
    return BlogPost(
        issue_number=issue_number,
        title=title,
        slug=slug,
        description=f"Description {issue_number}",
        created_date=published_at.date().isoformat(),
        published_at=published_at,
        updated_at=published_at,
        tags=(BlogTag(tag_name, tag_route.canonical_path),),
        body_html="<p>Body.</p>",
        route=routes.blog_detail(slug),
    )


def _render_quiet_adjacent_posts() -> dict[str, str]:
    settings = _settings("Quiet", page_size=2)
    routes = RouteRegistry(str(settings.site.url))
    posts = tuple(_local_blog(routes, *definition) for definition in _ADJACENT_POSTS)
    supporting_content = ContentCompiler(settings, route_registry=routes).compile(
        [
            _snap(
                2,
                "idea",
                'description: Idea.\ncreated_date: "2026-01-02"',
            ),
            _snap(
                10,
                "about",
                'description: About.\ncreated_date: "2026-01-03"',
            ),
        ]
    )
    content = ContentCompilationResult(
        blogs=posts,
        ideas=supporting_content.ideas,
        about=supporting_content.about,
        diagnostics=supporting_content.diagnostics,
    )
    site = SiteBuilder(settings, route_registry=routes).build(
        content,
        ProjectCompiler().compile(settings.projects, route=routes.projects()),
        build_start_time=datetime(2026, 1, 20, tzinfo=UTC),
    )
    assert not site.has_errors
    return RenderService(ThemeLoader(_ROOT).load(settings.theme)).render_site(site)


@pytest.mark.parametrize("theme", ["Escape1", "Escape2", "geoqiao.me", "Quiet"])
def test_theme_contract_renders_every_strict_page(theme: str) -> None:
    html = _render_theme(theme)
    assert set(html) >= {
        "index.html",
        "blog/index.html",
        "blog/post/index.html",
        "ideas/index.html",
        "ideas/2/index.html",
        "about/index.html",
        "projects/index.html",
        "tags/index.html",
        "atom.xml",
        "sitemap.xml",
        "robots.txt",
    }
    combined = "\n".join(value for key, value in html.items() if key.endswith(".html"))
    assert "issue-number" in combined and "2" in combined and "10" in combined
    assert "/templates/" + theme + "/static/" in combined
    assert "created_date:" not in combined and "slug:" not in combined
    assert "<script>alert" not in combined
    assert "idea-only" in html["ideas/2/index.html"]
    assert 'href="/tags/idea-only/"' not in combined
    assert "tags/idea-only/index.html" not in html
    assert 'href="/tags/python/"' in html["blog/post/index.html"]

    comment_pages = {
        "blog": ("blog/post/index.html", 1),
        "idea": ("ideas/2/index.html", 2),
        "about": ("about/index.html", 10),
    }
    for page_name, (output_path, issue_number) in comment_pages.items():
        rendered = html[output_path]
        assert rendered.count('id="comments-container"') == 1, page_name
        assert f'{theme}/static/js/comments.js" defer' in rendered, page_name
        assert f'data-issue-number="{issue_number}"' in rendered, page_name
        assert 'data-comments-repo="geoqiao/site"' in rendered, page_name
        assert 'data-comments-theme-mode="auto"' in rendered, page_name


@pytest.mark.parametrize("theme", ["Escape1", "Escape2", "geoqiao.me", "Quiet"])
def test_disabled_comments_leave_no_widget_or_dead_discussion_anchor(
    theme: str,
) -> None:
    rendered = _render_theme(theme, comments_enabled=False)
    for path, html in rendered.items():
        if not path.endswith(".html"):
            continue
        for absent in (
            "comments-container",
            "comments.js",
            "comments-loading",
            "comments-title",
            "utteranc.es",
            "<iframe",
            "Discuss",
        ):
            assert absent not in html, (path, absent)
    for path in ("blog/post/index.html", "ideas/2/index.html", "about/index.html"):
        assert "Body <strong>content</strong>." in rendered[path]


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_quiet_interface_is_english_without_translating_site_content(
    language: str,
) -> None:
    rendered = _render_theme("Quiet", language=language, title="中文站点")
    for path, html in rendered.items():
        if path.endswith(".html"):
            assert f'<html lang="{language}">' in html
            assert "中文站点" in html
            assert not re.search(r"[\u4e00-\u9fff]", html.replace("中文站点", ""))
    assert "Site index" in rendered["index.html"]
    assert "Writing, ideas, and things in the making." in rendered["index.html"]


def test_quiet_uses_profile_avatar_for_identity_about_and_favicon() -> None:
    avatar = "https://example.com/ada.webp"
    rendered = _render_theme("Quiet", author="Ada Lovelace", avatar=avatar)
    for path, html in rendered.items():
        if path.endswith(".html"):
            assert f'<link rel="icon" href="{avatar}">' in html
            assert f'class="identity-avatar" src="{avatar}" alt=""' in html
            assert "identity-mark" not in html
    assert f'class="profile-avatar" src="{avatar}"' in rendered["about/index.html"]
    fallback = _render_theme("Quiet", author="Ada Lovelace")["index.html"]
    assert ">AL</span>" in fallback
    assert 'href="/templates/Quiet/static/images/favicon.png"' in fallback


def test_idea_tag_public_context_is_display_only_not_a_blog_route() -> None:
    settings = _settings("geoqiao.me")
    routes = RouteRegistry(str(settings.site.url))
    content = ContentCompiler(settings, route_registry=routes).compile(
        [
            _snap(
                2,
                "idea",
                'description: Idea.\ncreated_date: "2026-01-02"',
                labels=("tag:idea-only", "TAG:IDEA-ONLY"),
            ),
            _snap(10, "about", 'description: About.\ncreated_date: "2026-01-03"'),
        ]
    )
    site = SiteBuilder(settings, routes).build(
        content,
        ProjectCompiler().compile([], route=routes.projects()),
        build_start_time=datetime(2026, 1, 20, tzinfo=UTC),
    )
    renderer = RenderService(ThemeLoader(_ROOT).load(settings.theme))
    assert renderer.env.loader is not None
    renderer.env.loader = ChoiceLoader(
        [
            DictLoader(
                {
                    "idea.html": "{% for tag in idea.tags %}<span>{{ tag.name }}</span>{% if tag.path is defined %}FALSE ROUTE{% endif %}{% endfor %}"
                }
            ),
            renderer.env.loader,
        ]
    )
    rendered = renderer.render_site(site)
    assert rendered["ideas/2/index.html"] == "<span>idea-only</span>"
    assert not site.tags.tags and not site.tag_archives
    assert routes.route_for_path("/tags/idea-only/") is None


def test_quiet_idea_tags_are_text_while_blog_tags_keep_their_archive() -> None:
    rendered = _render_theme("Quiet")
    tags = re.search(r'<ul class="tag-links".*?</ul>', rendered["ideas/2/index.html"])
    assert tags is not None
    assert "<span>idea-only</span>" in tags.group()
    assert "<span>python</span>" in tags.group()
    assert "href=" not in tags.group()
    assert "tags/idea-only/index.html" not in rendered
    assert 'href="/tags/python/"' in rendered["blog/post/index.html"]
    assert "tags/python/index.html" in rendered


def test_quiet_blog_adjacent_navigation_uses_global_sorted_routes() -> None:
    rendered = _render_quiet_adjacent_posts()

    newest = rendered["blog/newest/index.html"]
    assert 'class="article-end"' in newest
    assert "Previous" not in newest
    assert '<a rel="next" href="/blog/tie-high/"' in newest
    assert ">Next</a>" in newest

    middle = rendered["blog/tie-low/index.html"]
    assert (
        '<a rel="prev" href="/blog/tie-high/" aria-label="Previous: Tie &lt;high&gt; &amp; safe">'
        "Previous</a>"
    ) in middle
    assert (
        '<a rel="next" href="/blog/older/" aria-label="Next: Older post">Next</a>'
        in middle
    )

    oldest = rendered["blog/oldest/index.html"]
    assert (
        '<a rel="prev" href="/blog/older/" aria-label="Previous: Older post">Previous</a>'
        in oldest
    )
    assert "Next" not in oldest
    focus_tag = rendered["tags/focus/index.html"]
    assert (
        "Tie low" in focus_tag
        and "Newest post" in focus_tag
        and "Oldest post" in focus_tag
    )
    assert "Tie &lt;high&gt;" not in focus_tag and "Older post" not in focus_tag


def test_quiet_blog_footer_change_is_scoped_to_multi_post_blog_navigation() -> None:
    quiet = _render_theme("Quiet")
    blog = quiet["blog/post/index.html"]
    assert 'class="article-end"' not in blog
    assert "Back to Blog" not in blog
    assert "Back to top" not in blog
    assert 'class="breadcrumb"' in blog
    assert '<body id="top">' in blog
    assert "Back to Ideas" in quiet["ideas/2/index.html"]
    assert "Back to Home" in quiet["about/index.html"]

    for theme in ("Escape1", "Escape2", "geoqiao.me"):
        assert "Previous" not in _render_theme(theme)["blog/post/index.html"]
    assert "Back to Blog" in _render_theme("geoqiao.me")["blog/post/index.html"]


def test_named_site_routes_are_consumable_without_blogs_or_ideas() -> None:
    settings = _settings("Quiet")
    routes = RouteRegistry(str(settings.site.url))
    content = ContentCompiler(settings, route_registry=routes).compile(
        [_snap(10, "about", 'description: About.\ncreated_date: "2026-01-03"')]
    )
    site = SiteBuilder(settings, route_registry=routes).build(
        content,
        ProjectCompiler().compile(settings.projects, route=routes.projects()),
        build_start_time=datetime(2026, 1, 20, tzinfo=UTC),
    )
    assert not site.has_errors and not site.blogs and not site.ideas
    renderer = RenderService(ThemeLoader(_ROOT).load(settings.theme))
    rendered = renderer.render_site(site)
    names = ("home", "blog", "ideas", "about", "projects", "tags", "atom")
    for name in names:
        assert routes.route(name).output_path in rendered

    # A consumer template exercises the public context, not a private helper.
    assert renderer.env.loader is not None
    renderer.env.loader = ChoiceLoader(
        [
            DictLoader(
                {
                    "home.html": (
                        "{% for name in " + repr(names) + " %}"
                        "{% set route = site_routes[name] %}"
                        "{{ route.canonical_path }}|{{ route.output_path }}|"
                        "{{ route.canonical_url }}\n{% endfor %}"
                    )
                }
            ),
            renderer.env.loader,
        ]
    )
    renderer.env.cache.clear()
    probe = renderer.render_site(site)["index.html"]
    assert probe.splitlines() == [
        f"{route.canonical_path}|{route.output_path}|{route.canonical_url}"
        for name in names
        for route in [routes.route(name)]
    ]


class _RuntimeResourceProbe(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.resources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        if tag == "script":
            for key in ("src", "data-runtime-src"):
                if attributes.get(key):
                    self.resources.append(attributes[key])
        if tag == "link" and set(attributes.get("rel", "").split()) & {
            "stylesheet",
            "preconnect",
            "modulepreload",
            "preload",
        }:
            self.resources.append(attributes.get("href", ""))


@pytest.mark.parametrize("theme", ["Escape1", "Escape2", "geoqiao.me", "Quiet"])
def test_theme_runtime_dependencies_are_local_and_reproducible(theme: str) -> None:
    rendered = _render_theme(theme)
    probe = _RuntimeResourceProbe()
    for output_path, html in rendered.items():
        if output_path.endswith(".html"):
            probe.feed(html)

    assert not [
        resource
        for resource in probe.resources
        if resource.startswith(("https://", "http://", "//"))
    ]
    post = rendered["blog/post/index.html"]
    asset_url = f"/templates/{theme}/{_MERMAID_ASSET}"
    assert f'data-runtime-src="{asset_url}"' in post
    assert f'src="/templates/{theme}/static/js/mermaid.js"' in post

    loaded_theme = ThemeLoader(_ROOT).load(_settings(theme).theme)
    css_dir = loaded_theme.resource_root.joinpath("static/css")
    css = "\n".join(
        resource.read_text(encoding="utf-8")
        for resource in css_dir.iterdir()
        if resource.is_file() and resource.name.endswith(".css")
    )
    assert not re.search(r"@import\s+(?:url\()?['\"]?(?:https?:)?//", css)
    assert not re.search(
        r"@font-face\s*\{[^}]*url\(\s*['\"]?(?:https?:)?//",
        css,
        flags=re.DOTALL,
    )


@pytest.mark.parametrize("theme", ["Escape1", "Escape2", "geoqiao.me", "Quiet"])
def test_theme_favicon_is_a_valid_search_eligible_png(theme: str) -> None:
    favicon = (
        _ROOT / "src/escaping/themes" / theme / "static/images/favicon.png"
    ).read_bytes()

    assert favicon.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", favicon[16:24])
    assert width == height
    assert width >= 48


def _css_block(css: str, selector: str) -> str:
    match = re.search(
        rf"(?m)^{re.escape(selector)} \{{\n(.*?)\n^\}}", css, flags=re.DOTALL
    )
    assert match is not None, f"missing CSS rule: {selector}"
    return match.group(1)


def test_escape2_home_intro_is_the_thesis_without_identity_or_navigation() -> None:
    home = _render_theme(
        "Escape2",
        title="Site",
        bio="Profile copy",
        thesis=["Escaping is a static blog system based on GitHub Issues."],
    )["index.html"]

    assert (
        '<p class="intro-line">Escaping is a static blog system '
        "based on GitHub Issues.</p>" in home
    )
    assert "<h1" not in home
    assert "Profile copy" not in home
    assert 'class="nav-actions"' not in home
    assert 'class="authorImageWrapper"' not in home


def test_escape2_archive_rows_and_tags_are_unboxed() -> None:
    css = (_ROOT / "src/escaping/themes/Escape2/static/css/style.css").read_text(
        encoding="utf-8"
    )

    assert ".postListItem:hover" not in css
    row = _css_block(css, ".postListItem")
    assert "border-bottom: 1px solid var(--border);" in row
    for banned in (
        "background",
        "border-left",
        "border-radius",
        "transform",
        "transition",
        "box-shadow",
    ):
        assert banned not in row

    tag = _css_block(css, ".tag")
    for banned in ("border", "background", "padding", "box-shadow"):
        assert banned not in tag


def test_escape2_about_mark_falls_back_to_a_bundled_theme_asset() -> None:
    mark = "/templates/Escape2/static/images/author-mark.png"
    rendered = _render_theme("Escape2")

    assert (
        _ROOT / "src/escaping/themes/Escape2/static/images/author-mark.png"
    ).is_file()
    assert f'<img src="{mark}"' in rendered["about/index.html"]
    assert mark not in rendered["index.html"]

    avatar = "https://example.com/ada.png"
    configured = _render_theme("Escape2", avatar=avatar)["about/index.html"]
    assert f'<img src="{avatar}"' in configured
    assert mark not in configured


def test_configured_site_identity_reaches_homepage_search_signals() -> None:
    home = _render_theme("geoqiao.me", title="Geo Qiao", author="Geo Qiao")[
        "index.html"
    ]

    assert "<title>Geo Qiao</title>" in home
    assert '<meta property="og:site_name" content="Geo Qiao">' in home
    assert "<strong>Geo Qiao</strong>" in home

    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', home)
    assert match is not None
    graph = json.loads(match.group(1))["@graph"]
    website = next(item for item in graph if item["@type"] == "WebSite")
    assert website["name"] == "Geo Qiao"


def test_geoqiao_home_promotes_latest_post_without_profile_copy() -> None:
    home = _render_theme(
        "geoqiao.me",
        thesis=["Question assumptions.", "Build useful tools."],
        tagline="Analyst / tool builder",
    )["index.html"]

    assert '<section class="home-hero" aria-labelledby="home-title">' in home
    assert '<header class="home-intro">' in home
    assert '<h1 id="home-title">Site</h1>' in home
    assert '<article class="latest-story" aria-labelledby="latest-title">' in home
    assert '<h2 id="latest-title"><a href="/blog/post/">Blog</a></h2>' in home
    assert '<p class="latest-description">Post.</p>' in home
    assert '<a class="latest-read" href="/blog/post/">Read this issue' in home
    assert 'class="author-mark"' not in home
    assert "/static/images/author-mark.png" not in home
    assert "Question assumptions." not in home
    assert "Build useful tools." not in home
    assert "Analyst / tool builder" not in home


def test_geoqiao_home_has_one_visible_editorial_heading() -> None:
    home = _render_theme("geoqiao.me", thesis=[], tagline="")["index.html"]

    assert home.count("<h1") == 1
    assert 'id="home-title"' in home
    assert '<h2 id="latest-title">' in home
    assert 'class="profile-rail"' not in home


def test_geoqiao_author_images_prefer_the_configured_profile_avatar() -> None:
    avatar = "https://example.com/ada.png"
    rendered = _render_theme("geoqiao.me", author="Ada Lovelace", avatar=avatar)
    home = rendered["index.html"]
    post = rendered["blog/post/index.html"]
    about = rendered["about/index.html"]

    assert avatar not in home
    assert 'class="author-mark"' not in home
    for page in (post, about):
        assert f'src="{avatar}"' in page
        assert f'<img src="{avatar}" alt=""' in page
        assert "/static/images/author-mark.png" not in page
    for page in (home, post, about):
        assert "Geo Qiao" not in page
        assert ">GQ<" not in page
    assert 'aria-label="Ada Lovelace author mark"' in about


def test_geoqiao_theme_mark_fallback_has_no_identity_leaks() -> None:
    rendered = _render_theme("geoqiao.me", author="Ada Lovelace")
    home = rendered["index.html"]
    post = rendered["blog/post/index.html"]
    about = rendered["about/index.html"]

    assert "/static/images/author-mark.png" not in home
    assert 'class="author-mark"' not in home
    for page in (post, about):
        assert "/static/images/author-mark.png" in page
        assert 'static/images/author-mark.png" alt=""' in page
    for page in (home, post, about):
        assert "Geo Qiao" not in page
        assert ">GQ<" not in page
    assert 'aria-label="Ada Lovelace author mark"' in about


def test_geoqiao_about_body_is_the_only_owner_of_profile_copy() -> None:
    about = _render_theme(
        "geoqiao.me",
        bio="This profile copy must not repeat above the About body.",
    )["about/index.html"]

    assert "This profile copy must not repeat above the About body." not in about
    assert (
        '<div class="about-body post-content"><p>Body <strong>content</strong>.</p>'
        in about
    )


def test_shared_mermaid_loader_preserves_lazy_and_security_contract() -> None:
    script = (_ROOT / "src/escaping/static/mermaid.js").read_text(encoding="utf-8")

    assert "if (!loader || !runtimeSrc || !codeBlocks.length) return;" in script
    assert 'securityLevel: "strict"' in script
    assert "startOnLoad: false" in script


def test_geoqiao_theme_preserves_semantic_page_structure() -> None:
    html = _render_theme("geoqiao.me")
    home = html["index.html"]
    post = html["blog/post/index.html"]

    assert '<main class="site-main" id="main-content" tabindex="-1">' in home
    assert '<section class="home-hero" aria-labelledby="home-title">' in home
    assert '<header class="home-intro">' in home
    assert '<article class="latest-story" aria-labelledby="latest-title">' in home
    assert (
        '<section class="recent-writing" aria-labelledby="recent-writing-title">'
        in home
    )
    assert 'class="author-mark"' not in home
    assert '<article class="article-layout">' in post
    assert '<aside class="article-issue" aria-label="Article metadata">' in post
    assert '<nav data-article-toc aria-label="Article sections"></nav>' in post


def test_geoqiao_projects_stay_on_their_own_page() -> None:
    projects: list[dict[str, object]] = [
        {
            "slug": f"project-{index}",
            "title": f"Project {index}",
            "repository": f"geoqiao/project-{index}",
            "summary": f"Project {index} summary.",
            "order": index,
            "fallback_metadata": {"stars": stars, "language": "Python"},
        }
        for index, stars in enumerate((2, 13, 5, 8, 3, 21, 1))
    ]

    rendered = _render_theme("geoqiao.me", projects=projects)
    home = rendered["index.html"]
    project_page = rendered["projects/index.html"]

    assert "Project 5 ↗" not in home
    assert "Project 5 ↗" in project_page
    assert "Project 0 ↗" in project_page
    assert "★ 21" in project_page and "★ 13" in project_page


class _CurrentPageProbe(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.current_hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "a" and attributes.get("aria-current") == "page":
            self.current_hrefs.append(attributes.get("href") or "")


def test_geoqiao_navigation_marks_exactly_one_current_destination() -> None:
    rendered = _render_theme("geoqiao.me")
    expectations = {
        "index.html": "/",
        "blog/index.html": "/blog/",
        "blog/post/index.html": "/blog/",
    }

    for output_path, expected_href in expectations.items():
        probe = _CurrentPageProbe()
        probe.feed(rendered[output_path])
        assert probe.current_hrefs == [expected_href]


@pytest.mark.parametrize("theme", ["Escape1", "Escape2", "geoqiao.me", "Quiet"])
def test_profile_about_is_readable_safe_and_not_issue_content(
    theme: str, tmp_path: Path
) -> None:
    from escaping.artifact_validation import SiteArtifactValidator
    from escaping.models.content import ProfileAbout

    settings = Settings.model_validate(
        {
            **_settings(
                theme,
                author="Alice <Builder>",
                bio="Public <script>alert(1)</script> & bio",
            ).model_dump(),
            "about": {},
        }
    )
    routes = RouteRegistry(str(settings.site.url))
    content = ContentCompiler(settings, route_registry=routes).compile([])
    site = SiteBuilder(settings, routes).build(
        content,
        ProjectCompiler().compile([], route=routes.projects()),
        build_start_time=datetime(2026, 1, 20, tzinfo=UTC),
    )
    assert not site.has_errors and isinstance(site.about, ProfileAbout)
    renderer = RenderService(ThemeLoader(_ROOT).load(settings.theme))
    renderer.copy_theme_assets(tmp_path)
    rendered = renderer.render_site(site)
    about = rendered["about/index.html"]
    assert "Alice &lt;Builder&gt;" in about
    assert "Public &lt;script&gt;alert(1)&lt;/script&gt; &amp; bio" in about
    assert "<script>alert(1)" not in about
    schema = re.search(r'<script type="application/ld\+json">(.*?)</script>', about)
    assert schema is not None
    identity = json.loads(schema.group(1))
    assert identity["@type"] == "AboutPage" and identity["name"] == "Alice <Builder>"
    assert "mainEntity" not in identity  # A public owner may be an Organization.
    for absent in (
        "data-issue-number",
        "comments.js",
        "comments-container",
        "comments-title",
        "/issues/",
        "ISSUE",
        "<time",
        "BlogPosting",
        "datePublished",
    ):
        assert absent not in about
    for path, html in rendered.items():
        destination = tmp_path / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(html, encoding="utf-8")
    assert not SiteArtifactValidator(site).validate(tmp_path)
    target = tmp_path / "about/index.html"
    target.write_text(
        about.replace('"@type": "AboutPage"', '"@type": "BlogPosting"'),
        encoding="utf-8",
    )
    assert any(
        d.code == "PROFILE_ABOUT_IDENTITY"
        for d in SiteArtifactValidator(site).validate(tmp_path)
    )
