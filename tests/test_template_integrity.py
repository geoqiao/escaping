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
    bio: str = "",
    page_size: int | None = None,
    comments_enabled: bool = True,
    navigation_items: list[dict[str, str]] | None = None,
) -> Settings:
    site: dict[str, object] = {
        "title": title,
        "author": author,
        "url": "https://geoqiao.me/",
        "language": language,
        "navigation": {"items": [{"name": "Blog", "url": "/blog/"}]},
    }
    if navigation_items is not None:
        site["navigation"] = {"items": navigation_items}
    data: dict[str, object] = {
        "github": {"repo": "geoqiao/site", "allowed_authors": ["geoqiao"]},
        "site": site,
        "profile": {"avatar": avatar, "bio": bio},
        "about": {"issue_number": 10},
        "theme": {
            "source": "local",
            "name": theme,
            "path": "tests/fixtures/independent_theme",
        }
        if theme == "independent"
        else {"source": "builtin", "name": theme},
        "security": {"token_env": "TOKEN"},
        "comments": {"enabled": comments_enabled},
    }
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
    bio: str = "",
    comments_enabled: bool = True,
    navigation_items: list[dict[str, str]] | None = None,
) -> dict[str, str]:
    settings = _settings(
        theme,
        language=language,
        title=title,
        author=author,
        avatar=avatar,
        bio=bio,
        comments_enabled=comments_enabled,
        navigation_items=navigation_items,
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


@pytest.mark.parametrize("theme", ["Quiet", "independent"])
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


@pytest.mark.parametrize("theme", ["Quiet", "independent"])
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


class _MenuProbe(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.end_tag = ""
        self.links: list[tuple[str, str]] = []
        self.href: str | None = None
        self.label = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id") == "site-navigation":
            self.end_tag = tag
        if self.end_tag and tag == "a":
            self.href = values.get("href")
            self.label = ""

    def handle_data(self, data: str) -> None:
        if self.href is not None:
            self.label += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.href is not None:
            self.links.append(
                (self.label.strip().removeprefix("~/").rstrip(" ↗·"), self.href)
            )
            self.href = None
        if tag == self.end_tag:
            self.end_tag = ""


def test_quiet_menu_is_a_complete_override_independent_of_brand() -> None:
    for items in (
        [
            {"name": "Feed", "url": "/atom.xml"},
            {"name": "Start", "url": "/"},
            {"name": "Notes", "url": "/ideas/"},
        ],
        [{"name": "Notes", "url": "/ideas/"}],
        [],
    ):
        html = _render_theme("Quiet", navigation_items=items)["index.html"]
        probe = _MenuProbe()
        probe.feed(html)
        assert probe.links == [(item["name"], item["url"]) for item in items]
        assert 'class="identity" href="/"' in html
        assert ('aria-label="Toggle menu"' in html) is bool(items)
        assert 'href="#main-content"' in html
        if not items:
            assert 'id="site-navigation"' not in html


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
    assert "Writing and things in the making." in rendered["index.html"]


def test_quiet_uses_profile_avatar_only_for_identity_and_favicon() -> None:
    avatar = "https://example.com/ada.webp"
    rendered = _render_theme("Quiet", author="Ada Lovelace", avatar=avatar)
    for path, html in rendered.items():
        if path.endswith(".html"):
            assert f'<link rel="icon" href="{avatar}">' in html
            assert f'class="identity-avatar" src="{avatar}" alt=""' in html
            assert "identity-mark" not in html
    assert rendered["about/index.html"].count(f'src="{avatar}"') == 1
    assert 'class="about-page"' in rendered["about/index.html"]
    fallback = _render_theme("Quiet", author="Ada Lovelace")["index.html"]
    assert ">AL</span>" in fallback
    assert 'href="/templates/Quiet/static/images/favicon.png"' in fallback


def test_idea_tag_public_context_is_display_only_not_a_blog_route() -> None:
    settings = _settings("Quiet")
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


def test_quiet_runtime_dependencies_are_local_and_reproducible() -> None:
    theme = "Quiet"
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


def test_quiet_favicon_is_a_valid_search_eligible_png() -> None:
    favicon = (
        _ROOT / "src/escaping/themes/Quiet/static/images/favicon.png"
    ).read_bytes()

    assert favicon.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", favicon[16:24])
    assert width == height
    assert width >= 48


def test_configured_site_identity_reaches_homepage_search_signals() -> None:
    home = _render_theme("Quiet", title="Geo Qiao", author="Geo Qiao")["index.html"]

    assert "<title>Geo Qiao</title>" in home
    assert '<meta property="og:site_name" content="Geo Qiao">' in home
    assert "<strong>Geo Qiao</strong>" in home

    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', home)
    assert match is not None
    graph = json.loads(match.group(1))["@graph"]
    website = next(item for item in graph if item["@type"] == "WebSite")
    assert website["name"] == "Geo Qiao"


def test_shared_mermaid_loader_preserves_lazy_and_security_contract() -> None:
    script = (_ROOT / "src/escaping/static/mermaid.js").read_text(encoding="utf-8")

    assert "if (!loader || !runtimeSrc || !codeBlocks.length) return;" in script
    assert 'securityLevel: "strict"' in script
    assert "startOnLoad: false" in script


@pytest.mark.parametrize("theme", ["Quiet", "independent"])
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
