from __future__ import annotations

import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

import pytest

from github_blog.config import Settings
from github_blog.content_compiler import ContentCompiler
from github_blog.models.issue_snapshot import IssueSnapshot
from github_blog.projects import ProjectCompiler
from github_blog.services.render_service import RenderService
from github_blog.site_model import SiteModelBuilder


def _settings(theme: str) -> Settings:
    data: dict[str, object] = {
        "github": {"repo": "geoqiao/site", "allowed_authors": ["geoqiao"]},
        "site": {
            "title": "Site",
            "author": "geoqiao",
            "url": "https://geoqiao.me/",
            "navigation": {"items": [{"name": "Blog", "url": "/blog/"}]},
        },
        "about": {"issue_number": 10},
        "paths": {"theme": theme},
        "security": {"token_env": "TOKEN"},
    }
    return Settings.model_validate(data)


def _snap(
    number: int, kind: str, metadata: str, *, labels: tuple[str, ...] = ()
) -> IssueSnapshot:
    now = datetime(2026, 1, number, tzinfo=timezone.utc)
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


def _render_theme(theme: str) -> dict[str, str]:
    settings = _settings(theme)
    content = ContentCompiler(settings).compile(
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
    site = SiteModelBuilder(settings).build(
        content,
        ProjectCompiler().compile([]),
        build_start_time=datetime(2026, 1, 20, tzinfo=timezone.utc),
    )
    assert not site.has_errors
    return RenderService(settings).render_site(site)


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
    assert "MutationObserver" in combined
    assert "insertAdjacentHTML" in combined
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
        assert f"script.setAttribute('issue-number', '{issue_number}')" in rendered, (
            page_name
        )
        message_start = rendered.index("window.addEventListener('message'")
        message_end = rendered.index("\n    });", message_start)
        message_handler = rendered[message_start:message_end]
        assert "e.origin !== 'https://utteranc.es'" in message_handler, page_name
        assert "e.source !== iframe.contentWindow" in message_handler, page_name
        resize_start = message_handler.index("if (e.data.type === 'resize')")
        error_start = message_handler.index("} else if (e.data.type === 'error')")
        assert (
            "loadingMsg.style.display = 'none';"
            in message_handler[resize_start:error_start]
        ), page_name
        assert "e.data.type === 'error'" in message_handler, page_name
        assert "showError();" in message_handler[error_start:], page_name
        timeout_start = rendered.index("setTimeout(function()")
        timeout_end = rendered.index("}, 20000);", timeout_start)
        assert "showError();" in rendered[timeout_start:timeout_end], page_name


class _MobileNavigationProbe(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hamburger: dict[str, str | None] | None = None
        self.scripts: list[str] = []
        self._script_data: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "label" and "hamb" in (attributes.get("class") or "").split():
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


def test_geoqiao_theme_renders_approved_quiet_ledger_identity() -> None:
    html = _render_theme("geoqiao.me")
    home = html["index.html"]

    assert "演悲欢离合,当代岂无前代事?" in home
    assert "观抑扬褒贬,座中常有剧中人。" in home
    assert home.index('class="home-ledger-main"') < home.index('class="profile-rail"')
    assert "ISSUE #1" in home
    assert "prism-quiet-ledger.css" in home
    assert "prism-nord.css" not in home


@pytest.mark.parametrize("theme", ["Escape1", "Escape2", "geoqiao.me"])
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


def _css_rule(source: str, selector: str) -> str:
    match = re.search(rf"{re.escape(selector)}\s*\{{([^}}]*)\}}", source)
    if match is None:
        pytest.fail(f"missing CSS rule: {selector}")
    return match.group(1)


@pytest.mark.parametrize("theme", ["Escape1", "Escape2", "geoqiao.me"])
def test_theme_contains_local_overflow_contract(theme: str) -> None:
    css_path = Path("templates") / theme / "static" / "css" / "style.css"
    css = css_path.read_text(encoding="utf-8")

    table_rule = _css_rule(css, ".post-content table")
    pre_rule = _css_rule(css, ".post-content pre")
    assert "display: block" in table_rule
    assert "max-width: 100%" in table_rule
    assert "overflow-x: auto" in table_rule
    assert "overflow-x: auto" in pre_rule
