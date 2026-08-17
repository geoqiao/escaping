from __future__ import annotations

import json
import re
import struct
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

import pytest

from escaping.config import Settings
from escaping.content_compiler import ContentCompiler
from escaping.models.issue_snapshot import IssueSnapshot
from escaping.projects import ProjectCompiler
from escaping.routes import RouteRegistry
from escaping.services.render_service import RenderService
from escaping.site_builder import SiteBuilder
from escaping.theme import ThemeLoader

_ROOT = Path(__file__).parent.parent.absolute()
_MERMAID_VERSION = "11.16.1"
_MERMAID_ASSET = f"static/vendor/mermaid-{_MERMAID_VERSION}/mermaid.min.js"


def _settings(
    theme: str,
    *,
    title: str = "Site",
    author: str = "geoqiao",
    avatar: str = "",
    thesis: list[str] | None = None,
    tagline: str = "",
    bio: str = "",
    projects: list[dict[str, object]] | None = None,
) -> Settings:
    site: dict[str, object] = {
        "title": title,
        "author": author,
        "url": "https://geoqiao.me/",
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
    }
    if projects is not None:
        data["projects"] = projects
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
    title: str = "Site",
    author: str = "geoqiao",
    avatar: str = "",
    thesis: list[str] | None = None,
    tagline: str = "",
    bio: str = "",
    projects: list[dict[str, object]] | None = None,
) -> dict[str, str]:
    settings = _settings(
        theme,
        title=title,
        author=author,
        avatar=avatar,
        thesis=thesis,
        tagline=tagline,
        bio=bio,
        projects=projects,
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
            _snap(2, "idea", 'description: Idea.\ncreated_date: "2026-01-02"'),
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


@pytest.mark.parametrize("theme", ["Escape1", "Escape2", "geoqiao.me"])
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


@pytest.mark.parametrize("theme", ["Escape1", "Escape2", "geoqiao.me"])
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
    assert loaded_theme.resource_root.joinpath(_MERMAID_ASSET).is_file()
    assert loaded_theme.resource_root.joinpath(
        f"static/vendor/mermaid-{_MERMAID_VERSION}/LICENSE"
    ).is_file()

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


@pytest.mark.parametrize("theme", ["Escape1", "Escape2", "geoqiao.me"])
def test_theme_favicon_is_a_valid_search_eligible_png(theme: str) -> None:
    favicon = (
        _ROOT / "src/escaping/themes" / theme / "static/images/favicon.png"
    ).read_bytes()

    assert favicon.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", favicon[16:24])
    assert width == height
    assert width >= 48


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

    assert '<section class="home-hero" aria-labelledby="latest-title">' in home
    assert '<article class="latest-story">' in home
    assert '<p class="latest-description">Post.</p>' in home
    assert 'class="author-mark"' in home
    assert "/static/images/author-mark.png" in home
    assert "Question assumptions." not in home
    assert "Build useful tools." not in home
    assert "Analyst / tool builder" not in home


def test_geoqiao_home_has_one_visible_editorial_heading() -> None:
    home = _render_theme("geoqiao.me", thesis=[], tagline="")["index.html"]

    assert home.count("<h1") == 1
    assert 'id="latest-title"' in home
    assert 'class="profile-rail"' not in home


def test_geoqiao_author_images_prefer_the_configured_profile_avatar() -> None:
    avatar = "https://example.com/ada.png"
    rendered = _render_theme("geoqiao.me", author="Ada Lovelace", avatar=avatar)
    home = rendered["index.html"]
    post = rendered["blog/post/index.html"]
    about = rendered["about/index.html"]

    for page in (home, post, about):
        assert f'src="{avatar}"' in page
        assert f'<img src="{avatar}" alt=""' in page
        assert "/static/images/author-mark.png" not in page
        assert "Geo Qiao" not in page
        assert ">GQ<" not in page
    assert 'aria-label="Ada Lovelace author mark"' in home
    assert 'aria-label="Ada Lovelace author mark"' in about
    assert '<span class="author-mark-ghost" aria-hidden="true">AL</span>' in home


def test_geoqiao_theme_mark_fallback_has_no_identity_leaks() -> None:
    rendered = _render_theme("geoqiao.me", author="Ada Lovelace")
    home = rendered["index.html"]
    post = rendered["blog/post/index.html"]
    about = rendered["about/index.html"]

    for page in (home, post, about):
        assert "/static/images/author-mark.png" in page
        assert 'static/images/author-mark.png" alt=""' in page
        assert "Geo Qiao" not in page
        assert ">GQ<" not in page
    assert 'aria-label="Ada Lovelace author mark"' in home
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


def test_shared_comments_script_preserves_security_and_compatibility_contract() -> None:
    script = (_ROOT / "src/escaping/static/comments.js").read_text(encoding="utf-8")

    assert 'setAttribute("issue-number", issueNumber)' in script
    assert "Element.prototype.insertAdjacentHTML" in script
    assert "MutationObserver" in script
    assert 'removeAttribute("loading")' in script
    assert ".contentWindow.postMessage(" in script
    assert 'event.origin !== "https://utteranc.es"' in script
    assert "event.source !== iframe.contentWindow" in script
    assert "utterancesScript.onerror = function ()" in script
    assert 'event.data.type === "resize"' in script
    assert 'event.data.type === "error"' in script
    assert "if (!resizeReceived && loadingMsg) showError();" in script
    assert "}, 20000);" in script


def test_geoqiao_theme_preserves_semantic_page_structure() -> None:
    html = _render_theme("geoqiao.me")
    home = html["index.html"]
    post = html["blog/post/index.html"]

    assert '<main class="site-main" id="main-content" tabindex="-1">' in home
    assert '<section class="home-hero" aria-labelledby="latest-title">' in home
    assert (
        '<section class="recent-writing" aria-labelledby="recent-writing-title">'
        in home
    )
    assert '<figure class="author-mark" aria-label="geoqiao author mark">' in home
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
