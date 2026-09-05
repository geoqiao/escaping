from __future__ import annotations

import os
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any, Literal
from urllib.parse import quote

import pytest

_PLAYWRIGHT_PACKAGE_MESSAGE = (
    "Playwright Python package is required for browser tests; run `uv sync`."
)
try:
    pytest.importorskip("playwright.sync_api", reason=_PLAYWRIGHT_PACKAGE_MESSAGE)
except pytest.skip.Exception:
    if os.environ.get("CI", "").lower() == "true":
        pytest.fail(
            f"{_PLAYWRIGHT_PACKAGE_MESSAGE} CI must install dev dependencies.",
            pytrace=False,
        )
    raise

from playwright.sync_api import (  # noqa: E402
    Browser,
    Error,
    Page,
    Playwright,
    expect,
    sync_playwright,
)

from escaping.config import Settings  # noqa: E402
from escaping.content_compiler import ContentCompiler  # noqa: E402
from escaping.models.issue_snapshot import IssueSnapshot  # noqa: E402
from escaping.projects import ProjectCompiler  # noqa: E402
from escaping.routes import RouteRegistry  # noqa: E402
from escaping.services.render_service import RenderService  # noqa: E402
from escaping.site_builder import SiteBuilder  # noqa: E402
from escaping.theme import ThemeLoader  # noqa: E402

_ROOT = Path(__file__).parent.parent.absolute()
_THEMES = ("Escape1", "Escape2", "geoqiao.me", "Quiet")
_MERMAID_RENDER_TIMEOUT_MS = 15_000


def _browser_settings(theme: str) -> Settings:
    return Settings.model_validate(
        {
            "github": {"repo": "geoqiao/site", "allowed_authors": ["geoqiao"]},
            "site": {
                "title": "Browser Site",
                "author": "geoqiao",
                "url": "https://geoqiao.me/",
                "language": "zh-CN" if theme == "Quiet" else "en",
                "navigation": {
                    "items": [
                        {"name": "Blog", "url": "/blog/"},
                        {"name": "Ideas", "url": "/ideas/"},
                        {"name": "Projects", "url": "/projects/"},
                        {"name": "Tags", "url": "/tags/"},
                        {"name": "About", "url": "/about/"},
                    ]
                },
            },
            "profile": {"avatar": "/templates/Quiet/static/images/favicon.png"}
            if theme == "Quiet"
            else {},
            "about": {"issue_number": 10},
            "security": {"token_env": "TEST_TOKEN"},
            "theme": {"source": "builtin", "name": theme},
        }
    )


@pytest.fixture(scope="session")
def built_site_dirs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    build_time = datetime(2026, 1, 1, tzinfo=UTC)
    long_paragraph = " ".join(
        ["This section has enough prose to make scrolling observable."] * 24
    )
    wide_token = "unbroken-column-" + "x" * 180
    snapshots = [
        IssueSnapshot(
            number=1,
            title="我试了 6 款 Agent Orchestrator，这是我的最终选择",  # noqa: RUF001
            author="geoqiao",
            body=(
                "---\n"
                "slug: a-blog\n"
                "description: A blog post.\n"
                'created_date: "2026-01-01"\n'
                "---\n\nA blog post.\n\n"
                "## Opening Section\n\n"
                f"{long_paragraph}\n\n"
                "### 嵌套细节\n\n"
                f"{long_paragraph}\n\n"
                "## Closing Section\n\n"
                f"{long_paragraph}\n\n"
                "### Closing Detail\n\n"
                f"{long_paragraph}\n\n"
                f"| Name | Wide value |\n| --- | --- |\n| Example | {wide_token} |\n\n"
                f"```text\n{wide_token}\n```\n\n"
                "```mermaid\nflowchart LR\n  A[Local] --> B[Diagram]\n```"
            ),
            labels=("type:blog", "published", "tag:pi"),
            created_at=build_time,
            updated_at=build_time,
            is_pull_request=False,
        ),
        IssueSnapshot(
            number=2,
            title="An unfinished thought",
            author="geoqiao",
            body=(
                '---\ndescription: A short idea.\ncreated_date: "2026-01-01"\n---\n\n'
                "## A small observation\n\nIdeas can have a conversation too."
            ),
            labels=("type:idea", "published"),
            created_at=build_time,
            updated_at=build_time,
            is_pull_request=False,
        ),
        IssueSnapshot(
            number=10,
            title="About",
            author="geoqiao",
            body=(
                '---\ndescription: About.\ncreated_date: "2026-01-01"\n---\n\n'
                "About.\n\n## Things I Do\n\n- Build useful tools."
            ),
            labels=("type:about", "published"),
            created_at=build_time,
            updated_at=build_time,
            is_pull_request=False,
        ),
    ]
    output_dirs: dict[str, Path] = {}
    for theme in _THEMES:
        settings = _browser_settings(theme)
        routes = RouteRegistry(str(settings.site.url))
        content = ContentCompiler(settings, route_registry=routes).compile(snapshots)
        site = SiteBuilder(settings, route_registry=routes).build(
            content,
            ProjectCompiler().compile(settings.projects, route=routes.projects()),
            build_start_time=build_time,
        )
        assert not site.has_errors

        output_dir = tmp_path_factory.mktemp(f"browser-site-{theme}")
        renderer = RenderService(ThemeLoader(_ROOT).load(settings.theme))
        renderer.copy_theme_assets(output_dir)
        for output_path, html in renderer.render_site(site).items():
            path = output_dir / output_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(html, encoding="utf-8")
        output_dirs[theme] = output_dir
    return output_dirs


@pytest.fixture(scope="session")
def site_servers(built_site_dirs: dict[str, Path]) -> Iterator[dict[str, str]]:
    servers: list[ThreadingHTTPServer] = []
    server_threads: list[Thread] = []
    urls: dict[str, str] = {}
    for theme, output_dir in built_site_dirs.items():
        handler = partial(SimpleHTTPRequestHandler, directory=str(output_dir))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        servers.append(server)
        server_threads.append(server_thread)
        urls[theme] = f"http://127.0.0.1:{server.server_port}"
    try:
        yield urls
    finally:
        for server in servers:
            server.shutdown()
        for server_thread in server_threads:
            server_thread.join()
        for server in servers:
            server.server_close()


@pytest.fixture(scope="session")
def site_server(site_servers: dict[str, str]) -> str:
    return site_servers["geoqiao.me"]


@pytest.fixture(scope="session")
def playwright_api() -> Iterator[Playwright]:
    with sync_playwright() as playwright:
        yield playwright


@pytest.fixture(scope="session")
def browser(playwright_api: Playwright) -> Iterator[Browser]:
    message = (
        "Chromium is unavailable; install it with `uv run playwright install chromium`."
    )
    try:
        browser = playwright_api.chromium.launch()
    except Error as exc:
        if os.environ.get("CI", "").lower() == "true":
            raise
        pytest.skip(f"{message} ({exc})")
    try:
        yield browser
    finally:
        browser.close()


@pytest.fixture(scope="session")
def mobile_context_options(playwright_api: Playwright) -> dict[str, Any]:
    return dict(playwright_api.devices["iPhone 13"])


@pytest.fixture
def mobile_page(
    browser: Browser,
    site_server: str,
    mobile_context_options: dict[str, Any],
) -> Iterator[Page]:
    context = browser.new_context(**mobile_context_options)
    page = context.new_page()
    try:
        page.goto(f"{site_server}/", wait_until="load")
        yield page
    finally:
        context.close()


@pytest.fixture(params=_THEMES)
def theme_page(
    request: pytest.FixtureRequest,
    browser: Browser,
    site_servers: dict[str, str],
    mobile_context_options: dict[str, Any],
) -> Iterator[tuple[str, Page, str]]:
    theme = str(request.param)
    site_server = site_servers[theme]
    context = browser.new_context(**mobile_context_options)
    page = context.new_page()
    try:
        page.goto(f"{site_server}/", wait_until="load")
        yield theme, page, site_server
    finally:
        context.close()


def test_mobile_navigation_is_keyboard_operable_for_every_theme(
    theme_page: tuple[str, Page, str],
) -> None:
    _, page, _ = theme_page
    menu_control = page.get_by_role("button", name="Toggle menu")
    controlled_id = menu_control.get_attribute("aria-controls")
    assert controlled_id
    menu = page.locator(f"#{controlled_id}")
    blog_link = menu.get_by_role("link", name=re.compile(r"Blog$"))

    expect(menu_control).to_have_attribute("aria-expanded", "false")
    expect(blog_link).not_to_be_in_viewport()

    menu_control.focus()
    expect(menu_control).to_be_focused()
    page.keyboard.press("Enter")
    expect(menu_control).to_be_focused()
    expect(menu_control).to_have_attribute("aria-expanded", "true")
    expect(blog_link).to_be_in_viewport()

    blog_link.focus()
    expect(blog_link).to_be_focused()
    page.keyboard.press("Escape")
    expect(menu_control).to_have_attribute("aria-expanded", "false")
    expect(blog_link).not_to_be_in_viewport()
    expect(menu_control).to_be_focused()


def test_geoqiao_mobile_navigation_contains_focus_and_resets_cleanly(
    mobile_page: Page,
) -> None:
    menu_control = mobile_page.get_by_role(
        "button", name="Toggle menu", include_hidden=True
    )
    controlled_id = menu_control.get_attribute("aria-controls")
    assert controlled_id
    menu = mobile_page.locator(f"#{controlled_id}")
    menu_controls = menu.get_by_role("link").or_(menu.get_by_role("button"))
    blog_link = menu.get_by_role("link", name="Blog", exact=True)
    scrim = mobile_page.get_by_role("button", name="Close navigation")
    line = menu_control.locator('[aria-hidden="true"]')
    background_regions = (
        ".skip-link",
        ".ledger-brand",
        ".site-content",
        ".ledger-footer",
    )

    button_box = menu_control.bounding_box()
    line_box = line.bounding_box()
    assert button_box is not None and line_box is not None
    assert line_box["x"] + line_box["width"] / 2 == pytest.approx(
        button_box["x"] + button_box["width"] / 2, abs=2
    )
    assert line_box["y"] + line_box["height"] / 2 == pytest.approx(
        button_box["y"] + button_box["height"] / 2, abs=2
    )

    menu_control.focus()
    mobile_page.keyboard.press("Enter")
    expect(menu_control).to_have_attribute("aria-expanded", "true")
    expect(scrim).to_be_visible()
    for selector in background_regions:
        expect(mobile_page.locator(selector)).to_have_attribute("inert", "")

    for _ in range(menu_controls.count()):
        mobile_page.keyboard.press("Tab")
        assert mobile_page.evaluate(
            """() => {
                const active = document.activeElement;
                const menu = document.getElementById('header-nav');
                const toggle = document.querySelector('.hamb');
                return active === toggle || (menu && menu.contains(active));
            }"""
        )
        expect(mobile_page.locator("[inert]:focus, [inert] :focus")).to_have_count(0)

    mobile_page.keyboard.press("Escape")
    expect(menu_control).to_have_attribute("aria-expanded", "false")
    expect(scrim).to_be_hidden()
    expect(menu_control).to_be_focused()

    mobile_page.keyboard.press("Enter")
    expect(menu_control).to_have_attribute("aria-expanded", "true")
    scrim_box = scrim.bounding_box()
    assert scrim_box is not None
    scrim.click(position={"x": scrim_box["width"] / 2, "y": scrim_box["height"] - 1})
    expect(menu_control).to_have_attribute("aria-expanded", "false")
    expect(scrim).to_be_hidden()
    expect(menu_control).to_be_focused()

    mobile_page.keyboard.press("Enter")
    expect(menu_control).to_have_attribute("aria-expanded", "true")
    blog_link.focus()
    expect(blog_link).to_be_focused()
    mobile_page.set_viewport_size({"width": 1024, "height": 768})
    expect(menu_control).to_have_attribute("aria-expanded", "false")
    expect(scrim).to_be_hidden()
    expect(blog_link).to_be_focused()
    expect(mobile_page.locator("[inert]")).to_have_count(0)


def test_geoqiao_mobile_home_keeps_the_latest_story_readable_and_actionable(
    browser: Browser, site_server: str
) -> None:
    titles = (
        "我试了 6 款 Agent Orchestrator，这是我的最终选择",  # noqa: RUF001
        "从零开始搭建一个完全自动化的个人博客发布流水线",
        "AnUnusuallyLongUnbrokenAgentName",
    )
    for width, height in ((390, 844), (430, 932), (600, 844)):
        context = browser.new_context(viewport={"width": width, "height": height})
        page = context.new_page()
        try:
            page.goto(f"{site_server}/", wait_until="load")
            expect(page.locator(".author-mark")).to_have_count(0)
            expect(page.locator(".home-intro")).to_be_visible()
            read_link = page.get_by_role("link", name="Read this issue")
            expect(read_link).to_be_visible()
            read_link_box = read_link.bounding_box()
            recent_box = page.locator(".recent-writing").bounding_box()
            assert read_link_box is not None and recent_box is not None
            assert read_link_box["height"] >= 44
            assert recent_box["y"] <= height

            for title in titles:
                page.locator("#latest-title a").evaluate(
                    "(element, value) => { element.textContent = value; }", title
                )
                metrics = page.locator("#latest-title").evaluate(
                    """element => {
                        const range = document.createRange();
                        range.selectNodeContents(element);
                        const lines = new Set(
                            [...range.getClientRects()].map(rect => Math.round(rect.top))
                        );
                        return {
                            lines: lines.size,
                            scrollWidth: element.scrollWidth,
                            clientWidth: element.clientWidth,
                            pageScrollWidth: document.documentElement.scrollWidth,
                            pageClientWidth: document.documentElement.clientWidth,
                        };
                    }"""
                )
                assert metrics["lines"] <= 3
                assert metrics["scrollWidth"] <= metrics["clientWidth"] + 1
                assert metrics["pageScrollWidth"] <= metrics["pageClientWidth"] + 1

            if width == 600:
                page.goto(f"{site_server}/blog/a-blog/", wait_until="load")
                article_title = page.locator(".article-heading h1")
                article_title.evaluate(
                    "element => { element.textContent = "
                    "'从零开始搭建一个完全自动化的个人博客发布流水线'; }"
                )
                assert article_title.evaluate(
                    "element => element.scrollWidth <= element.clientWidth + 1"
                )
        finally:
            context.close()

    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    try:
        page.goto(f"{site_server}/", wait_until="load")
        expect(page.locator(".author-mark")).to_have_count(0)
        home_box = page.locator(".home-hero-inner").bounding_box()
        recent_box = page.locator(".recent-writing").bounding_box()
        recent_inner_box = page.locator(".recent-writing-inner").bounding_box()
        assert home_box is not None and recent_box is not None
        assert recent_inner_box is not None
        assert 760 <= home_box["width"] <= 840
        assert recent_inner_box["width"] == pytest.approx(home_box["width"], abs=1)
        assert recent_inner_box["x"] == pytest.approx(home_box["x"], abs=1)
        assert recent_box["y"] <= 660
        assert (
            page.locator("#latest-title").evaluate(
                "element => parseFloat(getComputedStyle(element).fontSize)"
            )
            <= 40.5
        )

        page.set_viewport_size({"width": 1920, "height": 1080})
        home_box = page.locator(".home-hero-inner").bounding_box()
        recent_inner_box = page.locator(".recent-writing-inner").bounding_box()
        assert home_box is not None and recent_inner_box is not None
        assert recent_inner_box["width"] == pytest.approx(home_box["width"], abs=1)
        assert recent_inner_box["x"] == pytest.approx(home_box["x"], abs=1)
    finally:
        context.close()


def test_theme_follows_system_until_the_user_chooses(mobile_page: Page) -> None:
    root = mobile_page.locator("html")
    menu = mobile_page.get_by_role("button", name="Toggle menu")
    toggle = mobile_page.locator(".theme-toggle")

    mobile_page.evaluate("localStorage.removeItem('theme')")
    mobile_page.emulate_media(color_scheme="dark")
    mobile_page.reload(wait_until="load")
    expect(root).to_have_attribute("data-theme", "dark")

    menu.click()
    expect(toggle).to_be_visible()
    toggle.click()
    expect(root).to_have_attribute("data-theme", "light")
    assert mobile_page.evaluate("localStorage.getItem('theme')") == "light"

    mobile_page.emulate_media(color_scheme="dark")
    expect(root).to_have_attribute("data-theme", "light")


def test_mermaid_diagram_uses_the_local_theme_runtime(
    mobile_page: Page, site_server: str
) -> None:
    mermaid_requests: list[str] = []
    mobile_page.on(
        "request",
        lambda request: (
            mermaid_requests.append(request.url) if "mermaid" in request.url else None
        ),
    )
    mobile_page.route("https://utteranc.es/**", lambda route: route.abort())

    mobile_page.goto(f"{site_server}/blog/a-blog/", wait_until="load")

    expect(mobile_page.locator("pre.mermaid svg")).to_have_count(
        1, timeout=_MERMAID_RENDER_TIMEOUT_MS
    )
    assert mermaid_requests
    assert all(request.startswith(site_server) for request in mermaid_requests)
    assert (
        sum(
            "/static/vendor/mermaid-11.16.1/mermaid.min.js" in request
            for request in mermaid_requests
        )
        == 1
    )


def test_geoqiao_article_toc_supports_nested_hash_navigation_and_active_state(
    browser: Browser, site_server: str
) -> None:
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page.route("https://utteranc.es/**", lambda route: route.abort())
    try:
        fragment = quote("嵌套细节", safe="")
        page.goto(f"{site_server}/blog/a-blog/#{fragment}", wait_until="load")

        toc = page.get_by_role("navigation", name="Article sections")
        nested_link = toc.get_by_role("link", name="嵌套细节", exact=True)
        other_nested_link = toc.get_by_role("link", name="Closing Detail", exact=True)
        nested_heading = page.get_by_role("heading", name="嵌套细节", exact=True)

        expect(nested_heading).to_be_in_viewport()
        expect(nested_link).to_be_visible()
        expect(nested_link).to_have_attribute("aria-current", "location")
        expect(toc.locator('[aria-current="location"]')).to_have_count(1)
        expect(other_nested_link).to_be_hidden()

        toc.get_by_role("link", name="Closing Section", exact=True).click()
        expect(other_nested_link).to_be_visible()
        expect(nested_link).to_be_hidden()
        other_nested_link.click()
        expect(page).to_have_url(re.compile(r"#closing-detail$"))
        expect(page.get_by_role("heading", name="Closing Detail")).to_be_in_viewport()
        expect(other_nested_link).to_have_attribute("aria-current", "location")
        expect(toc.locator('[aria-current="location"]')).to_have_count(1)
    finally:
        context.close()


def test_theme_long_form_content_has_local_overflow_and_a_readable_width(
    theme_page: tuple[str, Page, str],
) -> None:
    theme, page, site_server = theme_page
    page.route("https://utteranc.es/**", lambda route: route.abort())

    page.set_viewport_size({"width": 1440, "height": 900})
    for path in ("blog/a-blog/", "about/"):
        page.goto(f"{site_server}/{path}", wait_until="load")
        content_width = page.locator(".post-content").evaluate(
            "element => element.getBoundingClientRect().width"
        )
        assert 480 <= content_width <= 820

    if theme == "geoqiao.me":
        page.goto(f"{site_server}/blog/a-blog/", wait_until="load")
        article_box = page.locator(".article-main").bounding_box()
        assert article_box is not None
        assert 660 <= article_box["width"] <= 700
        assert abs(article_box["x"] + article_box["width"] / 2 - 720) <= 24

        page.goto(f"{site_server}/blog/", wait_until="load")
        index_box = page.locator(".index-page").bounding_box()
        first_row_box = page.locator(".editorial-row").first.bounding_box()
        assert index_box is not None and first_row_box is not None
        assert 760 <= index_box["width"] <= 840
        assert first_row_box["y"] <= 420
        assert first_row_box["height"] <= 100
        assert (
            page.get_by_role("heading", name="Blog", exact=True).evaluate(
                "element => parseFloat(getComputedStyle(element).fontSize)"
            )
            <= 56.5
        )

    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{site_server}/blog/a-blog/", wait_until="load")
    expect(page.locator("pre.mermaid svg")).to_have_count(
        1, timeout=_MERMAID_RENDER_TIMEOUT_MS
    )
    metrics = page.evaluate(
        """() => {
            const root = document.documentElement;
            const table = document.querySelector('.post-content table');
            const pre = document.querySelector('.post-content pre');
            const localOverflow = (element) =>
                [element, ...element.querySelectorAll('*')].some((candidate) => {
                    const overflowX = getComputedStyle(candidate).overflowX;
                    return candidate.scrollWidth > candidate.clientWidth &&
                        (overflowX === 'auto' || overflowX === 'scroll');
                });
            return {
                pageClientWidth: root.clientWidth,
                pageScrollWidth: root.scrollWidth,
                table: localOverflow(table),
                pre: localOverflow(pre),
            };
        }"""
    )
    assert metrics["pageScrollWidth"] <= metrics["pageClientWidth"] + 1
    for element_name in ("table", "pre"):
        assert metrics[element_name]

    if theme != "geoqiao.me":
        return

    page.goto(f"{site_server}/blog/", wait_until="load")
    blog_row = page.locator(".editorial-row").first
    blog_title_area = blog_row.locator(".editorial-copy")
    blog_title = blog_title_area.get_by_role("heading", level=2)
    row_box = blog_row.bounding_box()
    title_area_box = blog_title_area.bounding_box()
    assert row_box is not None and title_area_box is not None
    assert title_area_box["width"] == pytest.approx(row_box["width"], abs=1.5)
    assert (
        blog_title.evaluate("element => parseFloat(getComputedStyle(element).fontSize)")
        <= 22.5
    )
    assert page.evaluate(
        "document.documentElement.scrollWidth <= "
        "document.documentElement.clientWidth + 1"
    )

    page.goto(f"{site_server}/about/", wait_until="load")
    about_heading = page.locator(".about-heading")
    about_title = about_heading.get_by_role("heading", name="About", exact=True)
    about_mark = about_heading.get_by_role("figure", name=re.compile(r"author mark$"))
    about_body = page.locator(".about-body")
    about_section_title = about_body.get_by_role(
        "heading", name="Things I Do", exact=True
    )
    heading_box = about_heading.bounding_box()
    title_box = about_title.bounding_box()
    mark_box = about_mark.bounding_box()
    body_box = about_body.bounding_box()
    viewport = page.viewport_size
    assert heading_box is not None and body_box is not None
    assert title_box is not None and mark_box is not None
    assert viewport is not None
    assert heading_box["width"] == pytest.approx(body_box["width"], rel=0.1)
    assert heading_box["x"] == pytest.approx(body_box["x"], abs=8)
    assert title_box["x"] >= heading_box["x"] - 1
    assert mark_box["x"] + mark_box["width"] <= (
        heading_box["x"] + heading_box["width"] + 1
    )
    assert mark_box["width"] <= heading_box["width"] * 0.35
    assert mark_box["width"] <= viewport["width"] * 0.35
    assert (
        about_title.evaluate(
            "element => parseFloat(getComputedStyle(element).fontSize)"
        )
        <= viewport["width"] * 0.13
    )
    assert (
        about_section_title.evaluate(
            "element => parseFloat(getComputedStyle(element).fontSize)"
        )
        <= body_box["width"] * 0.08
    )
    assert title_box["y"] < mark_box["y"] + mark_box["height"]
    assert mark_box["y"] < title_box["y"] + title_box["height"]
    assert page.evaluate(
        "document.documentElement.scrollWidth <= "
        "document.documentElement.clientWidth + 1"
    )


@pytest.mark.parametrize("initial_mode", ["light", "dark"])
def test_quiet_mermaid_stays_readable_across_live_theme_changes(
    browser: Browser,
    site_servers: dict[str, str],
    initial_mode: Literal["light", "dark"],
) -> None:
    context = browser.new_context(color_scheme=initial_mode)
    page = context.new_page()
    page.route("https://utteranc.es/**", lambda route: route.abort())
    try:
        page.goto(f"{site_servers['Quiet']}/blog/a-blog/", wait_until="load")
        svg = page.locator("pre.mermaid svg")
        expect(svg).to_have_count(1, timeout=_MERMAID_RENDER_TIMEOUT_MS)
        original_id = svg.get_attribute("id")
        for _ in range(3):
            ratios = svg.evaluate(
                r"""svg => {
                    const inverted = getComputedStyle(svg).filter === 'invert(1)';
                    const rgb = (value, invert = inverted) => value.match(/\d+/g)
                        .slice(0, 3).map(Number).map(x => invert ? 255 - x : x);
                    const luminance = color => rgb(color).map(x => {
                        x /= 255;
                        return x <= .04045 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4;
                    }).reduce((sum, x, i) => sum + x * [.2126, .7152, .0722][i], 0);
                    const contrast = (a, b) => {
                        const [hi, lo] = [luminance(a), luminance(b)].sort((a,b) => b-a);
                        return (hi + .05) / (lo + .05);
                    };
                    const node = getComputedStyle(svg.querySelector('.node rect'));
                    const label = getComputedStyle(svg.querySelector('.nodeLabel'));
                    return {text: contrast(label.color, node.fill),
                        boundary: contrast(node.stroke, node.fill)};
                }"""
            )
            assert ratios["text"] >= 4.5 and ratios["boundary"] >= 3, ratios
            expected_filter = (
                "invert(1)"
                if page.locator("html").get_attribute("data-theme") == "dark"
                else "none"
            )
            assert svg.evaluate("x => getComputedStyle(x).filter") == expected_filter
            assert svg.get_attribute("id") == original_id
            page.get_by_role("button", name="Dark mode").click()
        page.emulate_media(media="print")
        assert svg.evaluate("x => getComputedStyle(x).filter") == "none"
        assert (
            page.locator("body").evaluate("x => getComputedStyle(x).backgroundColor")
            == "rgb(255, 255, 255)"
        )
    finally:
        context.close()


def test_quiet_reading_enhancements_and_appearance(
    browser: Browser, site_servers: dict[str, str]
) -> None:
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        permissions=["clipboard-read", "clipboard-write"],
    )
    page = context.new_page()
    page.route("https://utteranc.es/**", lambda route: route.abort())
    origin = site_servers["Quiet"]
    try:
        page.emulate_media(color_scheme="dark", reduced_motion="reduce")
        page.goto(f"{origin}/blog/a-blog/", wait_until="load")
        tag_box = page.locator(".article-heading .tag-links a").bounding_box()
        assert (
            tag_box is not None and tag_box["width"] >= 24 and tag_box["height"] >= 24
        )
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")
        page.emulate_media(color_scheme="light")
        expect(page.locator("html")).to_have_attribute("data-theme", "light")
        page.get_by_role("button", name="Dark mode").click()
        page.reload(wait_until="load")
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")
        expect(page.get_by_role("button", name="Dark mode")).to_have_attribute(
            "aria-pressed", "true"
        )

        toc = page.get_by_role("navigation", name="On this page")
        closing = toc.get_by_role("link", name="Closing Section", exact=True)
        closing.click()
        expect(page).to_have_url(re.compile(r"#closing-section$"))
        expect(page.get_by_role("heading", name="Closing Section")).to_be_in_viewport()
        expect(closing).to_have_attribute("aria-current", "location")
        expect(toc.locator('[aria-current="location"]')).to_have_count(1)
        page.reload(wait_until="load")
        expect(page.get_by_role("heading", name="Closing Section")).to_be_in_viewport()

        copy = page.locator(".copy-code")
        copy.click()
        expect(copy).to_have_text("Copied")
        assert "unbroken-column-" in page.evaluate("navigator.clipboard.readText()")
        page.evaluate(
            "Object.defineProperty(navigator, 'clipboard', {value: {"
            "writeText: () => Promise.reject(new Error('Denied'))}})"
        )
        copy.click()
        expect(copy).to_have_text("Select the code to copy manually")
        expect(page.locator(".comments-error")).to_contain_text(
            "View or add comment on GitHub"
        )

        page.set_viewport_size({"width": 390, "height": 844})
        table = page.get_by_role("table")
        table.focus()
        page.keyboard.press("ArrowRight")
        page.wait_for_function("document.querySelector('table').scrollLeft > 0")
        page.goto(f"{origin}/ideas/2/", wait_until="load")
        expect(
            page.get_by_role("heading", name="An unfinished thought")
        ).to_be_visible()
        expect(page.locator("#comments-container")).to_have_attribute(
            "data-issue-number", "2"
        )
        expect(page.locator(".toc")).not_to_have_attribute("open", "")
        page.locator(".toc summary").click()
        expect(page.get_by_role("link", name="A small observation")).to_be_visible()
    finally:
        context.close()


def test_quiet_without_javascript_keeps_content_and_navigation(
    browser: Browser, site_servers: dict[str, str]
) -> None:
    context = browser.new_context(
        java_script_enabled=False, viewport={"width": 320, "height": 700}
    )
    page = context.new_page()
    try:
        page.goto(site_servers["Quiet"], wait_until="load")
        expect(page.get_by_role("button", name="Toggle menu")).to_be_hidden()
        page.get_by_role("navigation", name="Main navigation").get_by_role(
            "link", name="Blog", exact=False
        ).click()
        page.get_by_role("heading", level=2).first.get_by_role("link").click()
        expect(page.get_by_role("heading", name="Opening Section")).to_be_visible()
        expect(
            page.locator(".comments-section").get_by_role("link", name="GitHub")
        ).to_have_attribute("href", "https://github.com/geoqiao/site/issues/1")
        expect(page.locator(".comments-loading")).to_be_hidden()
        expect(page.locator(".post-content table")).to_be_visible()
        expect(page.get_by_role("button", name="Copy code")).to_have_count(0)
    finally:
        context.close()


@pytest.mark.parametrize("viewport", [(390, 844), (320, 568)])
def test_quiet_mobile_menu_overlays_content_and_dismisses_cleanly(
    browser: Browser, site_servers: dict[str, str], viewport: tuple[int, int]
) -> None:
    page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
    try:
        page.goto(site_servers["Quiet"], wait_until="load")
        menu = page.get_by_role("button", name="Toggle menu", include_hidden=True)
        panel = page.locator("#" + str(menu.get_attribute("aria-controls")))
        content_box = page.locator("main").bounding_box()
        assert content_box is not None
        content_top = content_box["y"]
        menu.click()
        expect(menu).to_have_attribute("aria-expanded", "true")
        expect(panel).to_be_visible()
        content_box = page.locator("main").bounding_box()
        assert content_box is not None
        assert content_box["y"] == pytest.approx(content_top)
        bounds = panel.bounding_box()
        assert bounds is not None
        assert bounds["y"] + bounds["height"] <= viewport[1]
        assert panel.evaluate(
            "element => element.contains(document.elementFromPoint("
            "element.getBoundingClientRect().x + 20, "
            "element.getBoundingClientRect().y + 40))"
        )
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

        page.mouse.click(2, 120)
        expect(menu).to_have_attribute("aria-expanded", "false")
        expect(panel).to_be_hidden()
        menu.click()
        page.get_by_role("link", name="About me").focus()
        expect(panel).to_be_hidden()
        menu.click()
        page.keyboard.press("Escape")
        expect(panel).to_be_hidden()
        expect(menu).to_be_focused()

        menu.click()
        toggle = page.get_by_role("button", name="Dark mode")
        toggle.scroll_into_view_if_needed()
        expect(toggle).to_be_in_viewport()
        toggle.click()
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")
        page.set_viewport_size({"width": 1440, "height": 900})
        expect(menu).to_have_attribute("aria-expanded", "false")
        expect(panel).to_be_visible()
        page.set_viewport_size({"width": viewport[0], "height": viewport[1]})
        expect(panel).to_be_hidden()
        expect(menu).to_be_focused()
    finally:
        page.close()


def test_quiet_skip_focus_marks_heading_without_framing_the_page(
    browser: Browser, site_servers: dict[str, str]
) -> None:
    page = browser.new_page()
    try:
        page.goto(site_servers["Quiet"], wait_until="load")
        expect(page.get_by_role("banner")).to_have_count(1)
        skip_link = page.get_by_role("link", name="Skip to main content")
        page.keyboard.press("Tab")
        expect(skip_link).to_be_focused()
        expect(skip_link).to_have_css("outline-style", "solid")
        page.keyboard.press("Enter")
        main = page.locator("#main-content")
        expect(main).to_be_focused()
        expect(main).to_have_css("outline-style", "none")
        expect(main.locator("h1")).to_have_css("text-decoration-line", "underline")
        page.keyboard.press("Tab")
        expect(main).not_to_be_focused()
        expect(main.locator("h1")).to_have_css("text-decoration-line", "none")
    finally:
        page.close()
