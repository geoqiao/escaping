"""Theme contract: every Theme renders every page through the public pipeline.

The contract runs over the built-in Quiet, a Theme that extends it and an
independent Theme; the Quiet tests pin behavior of the default Theme.
"""

from __future__ import annotations

import json
import re
import struct
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

import pytest

from escpe.artifact_validation import SiteArtifactValidator, audit_seo
from escpe.config import Settings
from escpe.models.issue_snapshot import IssueSnapshot
from escpe.models.site import SiteModel
from escpe.site_compiler import check_theme, compile_site, prepare_theme, render_site

_ROOT = Path(__file__).parent.parent.absolute()
_NOW = datetime(2026, 1, 20, tzinfo=UTC)
_THEMES = {
    "quiet": "quiet",
    "extends": "tests/fixtures/extends_theme",
    "independent": "tests/fixtures/independent_theme",
}
_PROJECT = {
    "repository": "geoqiao/alpha",
    "slug": "alpha",
    "title": "Alpha",
    "summary": "A small tool.",
    "featured": True,
}


def _settings(
    theme: str = "quiet",
    *,
    site: Mapping[str, object] | None = None,
    options: Mapping[str, object] | None = None,
    **sections: object,
) -> Settings:
    return Settings.model_validate(
        {
            "github": {"repo": "geoqiao/site", "allowed_authors": ["geoqiao"]},
            "site": {
                "title": "Site",
                "author": "geoqiao",
                "url": "https://geoqiao.me/",
                "description": "Notes and tools.",
                "navigation": {"items": [{"name": "Blog", "url": "/blog/"}]},
                **(site or {}),
            },
            "about": {"issue_number": 10},
            "theme": {"use": _THEMES[theme], "options": options or {}},
            "comments": {"enabled": True},
            "projects": [_PROJECT],
            **sections,
        }
    )


def _issue(
    number: int,
    kind: str,
    *,
    title: str | None = None,
    fields: str = "",
    labels: tuple[str, ...] = (),
    day: int | None = None,
    body: str = "Body **content**.",
) -> IssueSnapshot:
    created = datetime(2026, 1, day or number, tzinfo=UTC)
    return IssueSnapshot(
        number,
        title or kind.title(),
        "geoqiao",
        f"---\n{fields}\n---\n\n{body}" if fields else body,
        ("published", f"type:{kind}", *labels),
        created,
        created,
        False,
    )


_CONTENT = (
    _issue(
        1,
        "blog",
        fields="slug: post\ndescription: Post.",
        labels=("tag:python",),
        body="Body **content**.\n\n```mermaid\ngraph LR\n  A --> B\n```\n",
    ),
    _issue(
        2,
        "idea",
        fields="description: Idea.",
        labels=("tag:idea-only", "tag:python"),
    ),
    _issue(10, "about", fields="description: About."),
)

_ADJACENT = (
    (4, "Tie low", "tie-low", 2, "focus"),
    (1, "Oldest post", "oldest", 1, "focus"),
    (11, "Newest post", "newest", 3, "focus"),
    (12, "Older post", "older", 1, "other"),
    (7, "Tie <high> & safe", "tie-high", 2, "other"),
)


def _adjacent_posts(descriptions: dict[int, str] | None = None) -> list[IssueSnapshot]:
    descriptions = descriptions or {}
    posts = [
        _issue(
            number,
            "blog",
            title=title,
            fields=f"slug: {slug}\ndescription: "
            + json.dumps(descriptions.get(number, f"Description {number}")),
            labels=(f"tag:{tag}",),
            day=day,
        )
        for number, title, slug, day, tag in _ADJACENT
    ]
    return [*posts, *_CONTENT[1:]]


def _build(
    output: Path, settings: Settings, content: Sequence[IssueSnapshot] = _CONTENT
) -> tuple[SiteModel, dict[str, str]]:
    theme, options = prepare_theme(settings, _ROOT)
    site = compile_site(
        settings, content, theme, project_enricher=None, build_start_time=_NOW
    )
    assert not site.has_errors and not site.skipped_issues, site.diagnostics
    rendered = render_site(output, site, theme, options)
    assert SiteArtifactValidator(site).validate(output) == []
    return site, rendered.files


def _pages(
    output: Path, settings: Settings, content: Sequence[IssueSnapshot] = _CONTENT
) -> dict[str, str]:
    _, files = _build(output, settings, content)
    return {path: text for path, text in files.items() if path.endswith(".html")}


@pytest.mark.parametrize("theme", list(_THEMES))
def test_theme_contract_renders_every_page_with_valid_links(
    theme: str, tmp_path: Path
) -> None:
    site, files = _build(tmp_path, _settings(theme))

    assert set(files) >= {
        "index.html",
        "blog/index.html",
        "blog/post/index.html",
        "ideas/index.html",
        "ideas/2/index.html",
        "about/index.html",
        "projects/index.html",
        "tags/index.html",
        "tags/python/index.html",
        "404.html",
        "atom.xml",
        "sitemap.xml",
        "robots.txt",
        "search.json",
    }
    assert audit_seo(site, tmp_path) == []
    for shared in ("comments.js", "mermaid.js", "mermaid/mermaid.min.js"):
        assert (tmp_path / "assets" / "escaping" / shared).is_file()

    pages = {path: text for path, text in files.items() if path.endswith(".html")}
    combined = "\n".join(pages.values())
    assert "slug: post" not in combined and "description: Post." not in combined
    assert "Body <strong>content</strong>." in pages["blog/post/index.html"]
    assert 'href="/tags/python/"' in pages["blog/post/index.html"]
    assert "idea-only" in pages["ideas/2/index.html"]
    assert 'href="/tags/idea-only/"' not in combined
    assert "tags/idea-only/index.html" not in files
    for path, number in (
        ("blog/post/index.html", 1),
        ("ideas/2/index.html", 2),
        ("about/index.html", 10),
    ):
        html = pages[path]
        assert html.count('id="comments-container"') == 1, path
        assert f'data-issue-number="{number}"' in html, path
        assert 'data-comments-repo="geoqiao/site"' in html, path
        assert 'data-comments-theme="github-light"' in html, path
        assert '<script src="/assets/escaping/comments.js" defer></script>' in html
    post = pages["blog/post/index.html"]
    assert 'src="/assets/escaping/mermaid.js"' in post
    assert 'data-runtime-src="/assets/escaping/mermaid/mermaid.min.js"' in post

    not_found = pages["404.html"]
    assert '<meta name="robots" content="noindex">' in not_found
    assert 'rel="canonical"' not in not_found and "og:url" not in not_found
    assert "404" not in files["sitemap.xml"]


@pytest.mark.parametrize("pages", [{}, {"ideas": False, "tags": False}])
@pytest.mark.parametrize("theme", list(_THEMES))
def test_theme_check_passes_with_sample_content(
    theme: str, pages: dict[str, bool]
) -> None:
    # With the tags pages off, tags have no path and show as text.
    result = check_theme(_settings(theme, pages=pages), config_root=_ROOT)

    assert result.success, result.diagnostics
    assert result.diagnostics == ()


@pytest.mark.parametrize("theme", list(_THEMES))
def test_disabled_comments_leave_no_widget_or_dead_discussion_anchor(
    theme: str, tmp_path: Path
) -> None:
    pages = _pages(tmp_path, _settings(theme, comments={"enabled": False}))

    for path, html in pages.items():
        for absent in (
            "comments-container",
            "comments.js",
            "comments-title",
            "utteranc.es",
            "<iframe",
            "Discuss",
        ):
            assert absent not in html, (path, absent)
    for path in ("blog/post/index.html", "ideas/2/index.html", "about/index.html"):
        assert "Body <strong>content</strong>." in pages[path]


@pytest.mark.parametrize("theme", list(_THEMES))
def test_profile_about_is_escaped_and_has_no_issue_features(
    theme: str, tmp_path: Path
) -> None:
    settings = _settings(
        theme,
        site={"author": "Alice <Builder>"},
        profile={"bio": "Public <script>alert(1)</script> & bio"},
        about={},
    )

    about = _pages(tmp_path, settings, _CONTENT[:2])["about/index.html"]

    assert "Alice &lt;Builder&gt;" in about
    assert "Public &lt;script&gt;alert(1)&lt;/script&gt; &amp; bio" in about
    assert "<script>alert(1)" not in about
    schema = re.search(r'<script type="application/ld\+json">(.*?)</script>', about)
    assert schema is not None
    identity = json.loads(schema.group(1))
    assert identity["@type"] == "AboutPage" and identity["name"] == "Alice <Builder>"
    for absent in ("data-issue-number", "comments.js", "/issues/", "<time", "Posting"):
        assert absent not in about


def test_a_theme_extending_quiet_overrides_partials_strings_and_assets(
    tmp_path: Path,
) -> None:
    settings = _settings(
        "extends",
        options={"now_text": "Reading <books>."},
        pages={"extra": [{"path": "/now/", "template": "now.html"}]},
    )

    pages = _pages(tmp_path, settings)

    for path, html in pages.items():
        assert '<meta name="x-now" content="Reading &lt;books&gt;.">' in html, path
        assert '<link rel="stylesheet" href="/assets/css/extra.css">' in html, path
        assert "Thanks for stopping by." in html, path
        assert "Thanks for reading." not in html, path
        assert 'class="site-surface"' in html, path
    home = pages["index.html"]
    assert '<p class="custom-intro">Custom introduction for geoqiao.' in home
    assert "my blog" not in home
    assert '<p class="now-text">Reading &lt;books&gt;.</p>' in pages["now/index.html"]
    assert (tmp_path / "assets/css/extra.css").is_file()
    assert (tmp_path / "assets/css/style.css").is_file()


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
            self.links.append((self.label.strip().rstrip(" ↗"), self.href))
            self.href = None
        if tag == self.end_tag:
            self.end_tag = ""


@pytest.mark.parametrize(
    "items",
    [
        [
            {"name": "Feed", "url": "/atom.xml"},
            {"name": "Start", "url": "/"},
            {"name": "Notes", "url": "/ideas/"},
        ],
        [{"name": "Notes", "url": "/ideas/"}],
        [],
    ],
)
def test_quiet_menu_is_exactly_the_configured_navigation(
    items: list[dict[str, str]], tmp_path: Path
) -> None:
    settings = _settings(site={"navigation": {"items": items}})

    html = _pages(tmp_path, settings)["blog/index.html"]

    probe = _MenuProbe()
    probe.feed(html)
    assert probe.links == [(item["name"], item["url"]) for item in items]
    assert 'class="identity" href="/"' in html
    assert ('aria-label="Toggle menu"' in html) is bool(items)
    assert ('id="site-navigation"' in html) is bool(items)
    assert 'href="#main-content"' in html


@pytest.mark.parametrize(
    ("language", "used", "expected", "absent"),
    [
        ("en", "en", ("Skip to main content", "Site index", "Recent Articles"), "站点"),
        ("zh-CN", "zh", ("跳到正文", "站点目录", "最近文章"), "Site index"),
    ],
)
def test_quiet_interface_strings_follow_the_site_language(
    language: str,
    used: str,
    expected: tuple[str, str, str],
    absent: str,
    tmp_path: Path,
) -> None:
    pages = _pages(tmp_path, _settings(site={"language": language}))

    for html in pages.values():
        assert f'<html lang="{language}">' in html
    skip, index, recent = expected
    blog = pages["blog/index.html"]
    assert f'<a class="skip-link" href="#main-content" lang="{used}">{skip}</a>' in blog
    assert index in blog and absent not in blog
    assert recent in pages["index.html"]
    # Site content is never translated.
    assert "Body <strong>content</strong>." in pages["blog/post/index.html"]


def test_quiet_accent_colors_reach_every_page(tmp_path: Path) -> None:
    options = {"accent_color": "#A72F6A", "accent_color_dark": "#e58bb6"}

    pages = _pages(tmp_path / "custom", _settings(options=options))

    for html in pages.values():
        assert ":root { --accent: #A72F6A; }" in html
        assert ':root[data-theme="dark"] { --accent: #e58bb6; }' in html
        assert ":root:not([data-theme]) { --accent: #e58bb6; }" in html
    default = _pages(tmp_path / "default", _settings())
    assert not any("--accent" in html for html in default.values())


def test_quiet_uses_profile_avatar_only_for_identity_and_favicon(
    tmp_path: Path,
) -> None:
    avatar = "https://example.com/ada.webp"
    settings = _settings(site={"author": "Ada Lovelace"}, profile={"avatar": avatar})

    pages = _pages(tmp_path / "avatar", settings)

    for path, html in pages.items():
        assert f'<link rel="icon" href="{avatar}">' in html
        avatar_class = "home-avatar" if path == "index.html" else "identity-avatar"
        assert f'class="{avatar_class}" src="{avatar}" alt=""' in html
        assert "identity-mark" not in html
    assert pages["about/index.html"].count(f'src="{avatar}"') == 1
    fallback = _pages(tmp_path / "fallback", _settings(site={"author": "Ada Lovelace"}))
    assert ">AL</span>" in fallback["blog/index.html"]
    assert (
        '<link rel="icon" href="/assets/images/favicon.png">' in fallback["index.html"]
    )


def test_quiet_idea_tags_are_text_while_blog_tags_keep_their_archive(
    tmp_path: Path,
) -> None:
    pages = _pages(tmp_path, _settings())

    tags = re.search(r'<ul class="tag-links".*?</ul>', pages["ideas/2/index.html"])
    assert tags is not None
    assert "<span>idea-only</span>" in tags.group()
    assert "<span>python</span>" in tags.group()
    assert "href=" not in tags.group()
    assert '<a href="/tags/python/">python</a>' in pages["blog/post/index.html"]


def test_quiet_blog_adjacent_navigation_uses_global_sorted_routes(
    tmp_path: Path,
) -> None:
    settings = _settings(paths={"page_size": 2})

    pages = _pages(tmp_path, settings, _adjacent_posts())

    newest = pages["blog/newest/index.html"]
    assert "Previous" not in newest
    assert '<a rel="next" href="/blog/tie-high/"' in newest
    middle = pages["blog/tie-low/index.html"]
    assert (
        '<a rel="prev" href="/blog/tie-high/" '
        'aria-label="Previous: Tie &lt;high&gt; &amp; safe">Previous</a>'
    ) in middle
    assert (
        '<a rel="next" href="/blog/older/" aria-label="Next: Older post">Next</a>'
        in middle
    )
    oldest = pages["blog/oldest/index.html"]
    assert '<a rel="prev" href="/blog/older/"' in oldest
    assert ">Next</a>" not in oldest
    focus = pages["tags/focus/index.html"]
    assert all(title in focus for title in ("Tie low", "Newest post", "Oldest post"))
    assert "Tie &lt;high&gt;" not in focus and "Older post" not in focus


def test_quiet_article_footers_fit_the_section(tmp_path: Path) -> None:
    pages = _pages(tmp_path, _settings())

    post = pages["blog/post/index.html"]
    assert 'class="article-end"' not in post  # a single post has no neighbors
    assert 'class="breadcrumb" href="/blog/"' in post
    assert '<body id="top">' in post
    assert "Back to Ideas" in pages["ideas/2/index.html"]
    assert "Back to Home" in pages["about/index.html"]


@pytest.mark.parametrize("selection", [None, [], [1, 7, 4]])
def test_quiet_home_keeps_featured_and_recent_writing(
    selection: list[int] | None, tmp_path: Path
) -> None:
    options: dict[str, object] = {"tagline": "Tools for my work."}
    if selection is not None:
        options["featured_posts"] = selection
    settings = _settings(
        options=options,
        profile={"bio": "Experiments & lessons."},
        paths={"page_size": 2},
    )

    pages = _pages(tmp_path, settings, _adjacent_posts())

    home = pages["index.html"]
    assert "Tools for my work." in home and "Experiments &amp; lessons." in home
    assert 'class="site-rail"' not in home
    intro = home.split('class="home-intro"', 1)[1].split("</div>", 1)[0]
    for path in ("/blog/", "/about/", "/projects/"):
        assert f'href="{path}"' in intro
    recent = home.split('aria-labelledby="recent-title"', 1)[1].split("</section>")[0]
    slugs = ["newest", "tie-high", "tie-low", "older", "oldest"]
    positions = [recent.index(f'href="/blog/{slug}/"') for slug in slugs]
    assert positions == sorted(positions)
    assert "Description " not in home and 'aria-label="Tags"' not in home
    if selection:
        featured = home.split('aria-labelledby="featured-title"', 1)[1]
        featured = featured.split("</section>", 1)[0]
        positions = [
            featured.index(f'href="/blog/{slug}/"')
            for slug in ("oldest", "tie-high", "tie-low")
        ]
        assert positions == sorted(positions)
        assert "Tie &lt;high&gt; &amp; safe" in featured
    else:
        assert 'id="featured-title"' not in home
    assert 'href="/blog/older/"' in pages["blog/page/2/index.html"]


def test_quiet_blog_descriptions_survive_pagination_as_plain_text(
    tmp_path: Path,
) -> None:
    content = _adjacent_posts({11: 'Tabs & "quotes" explained.'})

    pages = _pages(tmp_path, _settings(paths={"page_size": 2}), content)

    first = pages["blog/index.html"]
    assert (
        '<p class="entry-description">Tabs &amp; &#34;quotes&#34; explained.</p>'
        in first
    )
    assert '<p class="entry-description">Description 7</p>' in first
    second = pages["blog/page/2/index.html"]
    assert '<p class="entry-description">Description 4</p>' in second
    assert '<p class="entry-description">Description 12</p>' in second
    for path in ("index.html", "tags/focus/index.html"):
        assert 'class="entry-description"' not in pages[path]


def test_quiet_site_identity_reaches_homepage_search_signals(tmp_path: Path) -> None:
    settings = _settings(site={"title": "Geo Qiao", "author": "Geo Qiao"})

    home = _pages(tmp_path, settings)["index.html"]

    assert "<title>Geo Qiao</title>" in home
    assert '<meta property="og:site_name" content="Geo Qiao">' in home
    assert "<strong>Geo Qiao</strong>" in home
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', home)
    assert match is not None
    graph = json.loads(match.group(1))["@graph"]
    website = next(item for item in graph if item["@type"] == "WebSite")
    assert website["name"] == "Geo Qiao"
    assert website["url"] == "https://geoqiao.me/"


def test_quiet_social_image_metadata_covers_every_page(tmp_path: Path) -> None:
    seo = {
        "social_image": "/assets/images/favicon.png",
        "social_image_alt": 'Preview "art" & text',
    }

    configured = _pages(tmp_path / "set", _settings(seo=seo))

    image = "https://geoqiao.me/assets/images/favicon.png"
    alt = "Preview &#34;art&#34; &amp; text"
    for html in configured.values():
        assert f'<meta property="og:image" content="{image}">' in html
        assert f'<meta name="twitter:image" content="{image}">' in html
        assert '<meta name="twitter:card" content="summary_large_image">' in html
        assert f'<meta property="og:image:alt" content="{alt}">' in html
        assert f'<meta name="twitter:image:alt" content="{alt}">' in html
    for html in _pages(tmp_path / "unset", _settings()).values():
        assert "og:image" not in html and "twitter:image" not in html
        assert '<meta name="twitter:card" content="summary">' in html


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


def test_quiet_runtime_dependencies_are_local(tmp_path: Path) -> None:
    pages = _pages(tmp_path, _settings())

    probe = _RuntimeResourceProbe()
    for html in pages.values():
        probe.feed(html)
    assert probe.resources
    assert not [
        resource
        for resource in probe.resources
        if resource.startswith(("https://", "http://", "//"))
    ]
    css = "\n".join(
        path.read_text(encoding="utf-8") for path in tmp_path.glob("assets/**/*.css")
    )
    assert not re.search(r"@import\s+(?:url\()?['\"]?(?:https?:)?//", css)
    assert not re.search(
        r"@font-face\s*\{[^}]*url\(\s*['\"]?(?:https?:)?//", css, flags=re.DOTALL
    )


def test_quiet_favicon_is_a_valid_search_eligible_png() -> None:
    favicon = (_ROOT / "src/escpe/themes/quiet/static/images/favicon.png").read_bytes()

    assert favicon.startswith(b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", favicon[16:24])
    assert width == height and width >= 48


def test_shared_mermaid_loader_preserves_lazy_and_security_contract() -> None:
    script = (_ROOT / "src/escpe/static/mermaid.js").read_text(encoding="utf-8")

    assert "if (!loader || !runtimeSrc || !codeBlocks.length) return;" in script
    assert 'securityLevel: "strict"' in script
    assert "startOnLoad: false" in script
