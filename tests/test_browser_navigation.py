from __future__ import annotations

import os
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
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
_THEMES = ("Escape1", "Escape2", "geoqiao.me")


def _browser_settings(theme: str) -> Settings:
    return Settings.model_validate(
        {
            "github": {"repo": "geoqiao/site", "allowed_authors": ["geoqiao"]},
            "site": {
                "title": "Browser Site",
                "author": "geoqiao",
                "url": "https://geoqiao.me/",
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
            title="A Blog",
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
            labels=("type:blog", "published"),
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
def browser() -> Iterator[Browser]:
    message = (
        "Chromium is unavailable; install it with `uv run playwright install chromium`."
    )
    with sync_playwright() as playwright_api:
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


@pytest.fixture
def mobile_page(browser: Browser, site_server: str) -> Iterator[Page]:
    context = browser.new_context(viewport={"width": 390, "height": 844})
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
) -> Iterator[tuple[str, Page, str]]:
    theme = str(request.param)
    site_server = site_servers[theme]
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    try:
        page.goto(f"{site_server}/", wait_until="load")
        yield theme, page, site_server
    finally:
        context.close()


def test_mobile_navigation_is_keyboard_operable_for_every_theme(
    theme_page: tuple[str, Page, str],
) -> None:
    theme, page, _ = theme_page
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

    page.keyboard.press("Escape" if theme == "geoqiao.me" else "Enter")
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
    assert mobile_page.locator("[inert]").count() > 0

    for _ in range(menu_controls.count() + 1):
        mobile_page.keyboard.press("Tab")
        expect(mobile_page.locator("[inert]:focus, [inert] :focus")).to_have_count(0)

    mobile_page.keyboard.press("Escape")
    expect(menu_control).to_have_attribute("aria-expanded", "false")
    expect(scrim).to_be_hidden()
    expect(menu_control).to_be_focused()

    mobile_page.keyboard.press("Enter")
    expect(menu_control).to_have_attribute("aria-expanded", "true")
    scrim.click()
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

    expect(mobile_page.locator("pre.mermaid svg")).to_have_count(1)
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

    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{site_server}/blog/a-blog/", wait_until="load")
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
    row_box = blog_row.bounding_box()
    title_area_box = blog_title_area.bounding_box()
    assert row_box is not None and title_area_box is not None
    assert title_area_box["width"] >= row_box["width"] * 0.78
    assert page.evaluate(
        "document.documentElement.scrollWidth <= "
        "document.documentElement.clientWidth + 1"
    )

    page.goto(f"{site_server}/about/", wait_until="load")
    about_heading = page.locator(".about-heading")
    about_title = about_heading.get_by_role("heading", name="About", exact=True)
    about_mark = about_heading.get_by_role("figure", name=re.compile(r"author mark$"))
    about_body = page.locator(".about-body")
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
    assert mark_box["width"] <= heading_box["width"] * 0.4
    assert mark_box["width"] <= viewport["width"] * 0.4
    assert title_box["y"] < mark_box["y"] + mark_box["height"]
    assert mark_box["y"] < title_box["y"] + title_box["height"]
    assert page.evaluate(
        "document.documentElement.scrollWidth <= "
        "document.documentElement.clientWidth + 1"
    )
