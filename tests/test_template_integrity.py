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


def _settings(
    theme: str,
    *,
    title: str = "Site",
    author: str = "geoqiao",
    thesis: list[str] | None = None,
    tagline: str = "",
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
        "profile": {"tagline": tagline},
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
    thesis: list[str] | None = None,
    tagline: str = "",
    projects: list[dict[str, object]] | None = None,
) -> dict[str, str]:
    settings = _settings(
        theme,
        title=title,
        author=author,
        thesis=thesis,
        tagline=tagline,
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


def test_geoqiao_home_renders_configured_thesis_lines_and_profile_tagline() -> None:
    home = _render_theme(
        "geoqiao.me",
        thesis=["Question assumptions.", "Build useful tools."],
        tagline="Analyst / tool builder",
    )["index.html"]

    assert (
        '<h1 id="home-thesis"><span>Question assumptions.</span>'
        "<span>Build useful tools.</span></h1>"
    ) in home
    assert '<p class="profile-role">Analyst / tool builder</p>' in home


def test_geoqiao_home_omits_unconfigured_thesis_and_tagline() -> None:
    home = _render_theme("geoqiao.me", thesis=[], tagline="")["index.html"]

    assert 'class="ledger-hero"' not in home
    assert 'id="home-thesis"' not in home
    assert 'class="profile-role"' not in home


def test_shared_comments_script_preserves_browser_contract() -> None:
    script = (_ROOT / "src/escaping/static/comments.js").read_text(encoding="utf-8")

    assert "Element.prototype.insertAdjacentHTML" in script
    assert "MutationObserver" in script
    assert 'removeAttribute("loading")' in script
    assert ".contentWindow.postMessage(" in script
    assert 'event.origin !== "https://utteranc.es"' in script
    assert "event.source !== iframe.contentWindow" in script
    assert 'event.data.type === "resize"' in script
    assert 'loadingMsg.style.display = "none"' in script
    assert 'event.data.type === "error"' in script
    assert "showError();" in script
    assert "}, 20000);" in script


class _MobileNavigationProbe(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hamburger_tag: str | None = None
        self.hamburger: dict[str, str | None] | None = None
        self.scripts: list[str] = []
        self._script_data: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if (
            tag in {"button", "label"}
            and "hamb" in (attributes.get("class") or "").split()
        ):
            self.hamburger_tag = tag
            self.hamburger = attributes
        if tag == "script":
            self._script_data = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._script_data is not None:
            self.scripts.append("".join(self._script_data))
            self._script_data = None

    def handle_data(self, data: str) -> None:
        if self._script_data is not None:
            self._script_data.append(data)


def test_geoqiao_theme_preserves_semantic_page_structure() -> None:
    html = _render_theme("geoqiao.me")
    home = html["index.html"]
    post = html["blog/post/index.html"]

    assert '<main class="site-main" id="main-content" tabindex="-1">' in home
    assert '<section class="recent-posts" aria-labelledby="recent-posts-title">' in home
    assert '<aside class="profile-rail" aria-label="Site profile">' in home
    assert '<article class="article-layout">' in post
    assert '<aside class="article-issue" aria-label="Article metadata">' in post
    assert '<nav data-article-toc aria-label="Article sections"></nav>' in post


def test_geoqiao_theme_uses_local_stylesheets_and_exposes_accent_token() -> None:
    home = _render_theme("geoqiao.me")["index.html"]
    css = (
        ThemeLoader(_ROOT)
        .load(_settings("geoqiao.me").theme)
        .read_text("static/css/style.css")
    )

    stylesheet_hrefs = re.findall(
        r'<link rel="stylesheet" href="([^"]+)">',
        home,
    )
    assert stylesheet_hrefs
    assert all(
        href.startswith("/templates/geoqiao.me/static/") for href in stylesheet_hrefs
    )
    assert not re.search(r"""@import\s+(?:url\()?['"]?(?:https?:)?//""", css)
    assert not re.search(
        r"@font-face\s*\{[^}]*(?:https?:)?//",
        css,
        flags=re.DOTALL,
    )
    assert re.search(r"--ledger-accent\s*:\s*\S[^;]*", _css_rule(css, ":root"))


def test_geoqiao_article_toc_tracks_nested_sections_and_hash_navigation() -> None:
    post = _render_theme("geoqiao.me")["blog/post/index.html"]

    assert (
        'document.querySelectorAll(".article-main .post-content h2, .article-main .post-content h3")'
        in post
    )
    assert 'className = "toc-group"' in post
    assert 'className = "toc-children"' in post
    assert "link.title = heading.textContent" in post
    assert 'link.setAttribute("aria-current", "location")' in post
    assert 'group.element.classList.toggle("is-expanded"' in post
    assert "hashId = decodeURIComponent(hashId)" in post
    assert "hashTarget.scrollIntoView()" in post


def test_geoqiao_home_renders_five_configured_projects_ranked_by_stars() -> None:
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

    home = _render_theme("geoqiao.me", projects=projects)["index.html"]

    ranked_titles = ("Project 5", "Project 1", "Project 3", "Project 2", "Project 4")
    positions = [home.index(f">{title} ↗</a>") for title in ranked_titles]
    assert positions == sorted(positions)
    assert "Project 0 ↗" not in home
    assert "Project 6 ↗" not in home
    assert "★ 21" in home and "★ 13" in home
    assert '<a href="/projects/">VIEW ALL →</a>' in home


@pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
def test_mobile_navigation_is_keyboard_operable(theme: str) -> None:
    probe = _MobileNavigationProbe()
    probe.feed(_render_theme(theme)["index.html"])

    assert probe.hamburger is not None
    assert probe.hamburger["for"] == "side-menu"
    assert probe.hamburger["role"] == "button"
    assert probe.hamburger["tabindex"] == "0"
    assert probe.hamburger["aria-expanded"] == "false"
    assert probe.hamburger["aria-controls"] == "header-nav"

    inline_scripts = "\n".join(probe.scripts)
    assert "label.addEventListener('keydown'" in inline_scripts
    assert "event.key === 'Enter'" in inline_scripts
    assert "event.key === ' '" in inline_scripts
    assert "event.preventDefault()" in inline_scripts
    assert "checkbox.checked = !checkbox.checked" in inline_scripts
    assert "checkbox.addEventListener('change'" in inline_scripts
    assert "label.setAttribute('aria-expanded'" in inline_scripts


def test_geoqiao_mobile_navigation_uses_native_button_and_current_page_state() -> None:
    html = _render_theme("geoqiao.me")
    home = html["index.html"]
    blog = html["blog/index.html"]
    probe = _MobileNavigationProbe()
    probe.feed(home)

    assert probe.hamburger_tag == "button"
    assert probe.hamburger is not None
    assert probe.hamburger["type"] == "button"
    assert probe.hamburger["aria-expanded"] == "false"
    assert probe.hamburger["aria-controls"] == "header-nav"
    assert 'class="side-menu"' not in home

    inline_scripts = "\n".join(probe.scripts)
    assert "menuButton.addEventListener('click'" in inline_scripts
    assert "menuButton.setAttribute('aria-expanded'" in inline_scripts
    assert "label.addEventListener('keydown'" not in inline_scripts

    assert len(re.findall(r'aria-current="page"', home)) == 1
    assert re.search(r'class="ledger-nav-link nav-home"[^>]+aria-current="page"', home)
    assert len(re.findall(r'aria-current="page"', blog)) == 1
    assert re.search(r'class="ledger-nav-link nav-blog"[^>]+aria-current="page"', blog)
    assert re.search(
        r'<meta name="theme-color" content="[^"]+" id="theme-color">', home
    )
    article = html["blog/post/index.html"]
    assert len(re.findall(r'aria-current="page"', article)) == 1
    assert re.search(
        r'class="ledger-nav-link nav-blog"[^>]+aria-current="page"', article
    )


def _css_rule(source: str, selector: str) -> str:
    match = re.search(rf"{re.escape(selector)}\s*\{{([^}}]*)\}}", source)
    if match is None:
        pytest.fail(f"missing CSS rule: {selector}")
    return match.group(1)


@pytest.mark.parametrize("theme", ["Escape1", "Escape2", "geoqiao.me"])
def test_theme_contains_local_overflow_contract(theme: str) -> None:
    settings = _settings(theme)
    css = ThemeLoader(_ROOT).load(settings.theme).read_text("static/css/style.css")

    table_rule = _css_rule(css, ".post-content table")
    pre_rule = _css_rule(css, ".post-content pre")
    assert "display: block" in table_rule
    assert "max-width:" in table_rule
    assert "overflow-x: auto" in table_rule
    assert "overflow-x: auto" in pre_rule
