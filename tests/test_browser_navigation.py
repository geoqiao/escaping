from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

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


def _browser_settings() -> Settings:
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
            "theme": {"source": "builtin", "name": "geoqiao.me"},
        }
    )


@pytest.fixture(scope="session")
def built_site_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    settings = _browser_settings()
    build_time = datetime(2026, 1, 1, tzinfo=UTC)
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
                "---\n\nA blog post."
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
                '---\ndescription: About.\ncreated_date: "2026-01-01"\n---\n\nAbout.'
            ),
            labels=("type:about", "published"),
            created_at=build_time,
            updated_at=build_time,
            is_pull_request=False,
        ),
    ]
    routes = RouteRegistry(str(settings.site.url))
    content = ContentCompiler(settings, route_registry=routes).compile(snapshots)
    site = SiteBuilder(settings, route_registry=routes).build(
        content,
        ProjectCompiler().compile(settings.projects, route=routes.projects()),
        build_start_time=build_time,
    )
    assert not site.has_errors

    output_dir = tmp_path_factory.mktemp("browser-site")
    renderer = RenderService(ThemeLoader(_ROOT).load(settings.theme))
    renderer.copy_theme_assets(output_dir)
    for output_path, html in renderer.render_site(site).items():
        path = output_dir / output_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
    return output_dir


@pytest.fixture(scope="session")
def site_server(built_site_dir: Path) -> Iterator[str]:
    handler = partial(SimpleHTTPRequestHandler, directory=str(built_site_dir))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server_thread.join()
        server.server_close()


@pytest.fixture
def mobile_page(site_server: str) -> Iterator[Page]:
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

        context = browser.new_context(**playwright_api.devices["iPhone 13"])
        page = context.new_page()
        try:
            page.goto(f"{site_server}/", wait_until="load")
            yield page
        finally:
            context.close()
            browser.close()


def test_mobile_navigation_user_journey(mobile_page: Page) -> None:
    menu_button = mobile_page.get_by_role("button", name="Toggle menu")
    menu_button_dom = mobile_page.locator(".hamb")
    navigation = mobile_page.get_by_role("navigation", name="Primary navigation")
    blog_link = navigation.get_by_role("link", name="Blog", exact=True)
    scrim = mobile_page.get_by_role("button", name="Close navigation")
    background_regions = mobile_page.locator(
        ".skip-link, .ledger-brand, .site-content, .ledger-footer"
    )
    background_focus = mobile_page.locator(
        ".skip-link:focus, .ledger-brand:focus, .site-content:focus, "
        ".site-content :focus, .ledger-footer:focus, .ledger-footer :focus"
    )

    expect(menu_button).to_have_attribute("aria-expanded", "false")
    expect(blog_link).not_to_be_visible()

    menu_button.focus()
    mobile_page.keyboard.press("Enter")
    expect(menu_button).to_have_attribute("aria-expanded", "true")
    expect(blog_link).to_be_visible()

    mobile_page.keyboard.press("Shift+Tab")
    expect(background_focus).to_have_count(0)
    menu_button.focus()

    navigation_controls = navigation.locator("a, button")
    for _ in range(navigation_controls.count() + 1):
        mobile_page.keyboard.press("Tab")
        expect(background_focus).to_have_count(0)
    for index in range(background_regions.count()):
        expect(background_regions.nth(index)).to_have_attribute("inert", "")

    mobile_page.keyboard.press("Escape")
    expect(menu_button).to_have_attribute("aria-expanded", "false")
    expect(scrim).to_be_hidden()
    expect(menu_button).to_be_focused()

    mobile_page.keyboard.press("Enter")
    expect(menu_button).to_have_attribute("aria-expanded", "true")
    expect(scrim).to_be_visible()
    scrim_box = scrim.bounding_box()
    assert scrim_box is not None
    scrim.click(position={"x": scrim_box["width"] / 2, "y": scrim_box["height"] - 1})
    expect(menu_button).to_have_attribute("aria-expanded", "false")
    expect(scrim).to_be_hidden()
    expect(menu_button).to_be_focused()

    mobile_page.keyboard.press("Enter")
    expect(menu_button).to_have_attribute("aria-expanded", "true")
    blog_link.focus()
    expect(blog_link).to_be_focused()
    mobile_page.set_viewport_size({"width": 1024, "height": 768})
    expect(menu_button_dom).to_have_attribute("aria-expanded", "false")
    expect(scrim).to_be_hidden()
    expect(blog_link).to_be_focused()
    for index in range(background_regions.count()):
        expect(background_regions.nth(index)).not_to_have_attribute("inert")


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


def test_mobile_blog_titles_use_the_full_row_and_navigation_is_centered(
    mobile_page: Page, site_server: str
) -> None:
    mobile_page.goto(f"{site_server}/blog/", wait_until="load")
    row = mobile_page.locator(".editorial-row").first
    copy = row.locator(".editorial-copy")
    title = copy.locator("h2")
    menu = mobile_page.locator(".hamb")
    menu_line = menu.locator(".hamb-line")

    row_box = row.bounding_box()
    copy_box = copy.bounding_box()
    menu_box = menu.bounding_box()
    line_box = menu_line.bounding_box()
    assert row_box is not None and copy_box is not None
    assert menu_box is not None and line_box is not None
    assert copy_box["width"] == pytest.approx(row_box["width"], abs=1)
    assert (
        title.evaluate("element => parseFloat(getComputedStyle(element).fontSize)")
        <= 22
    )
    assert menu.evaluate("element => getComputedStyle(element).display") == "grid"
    assert line_box["x"] + line_box["width"] / 2 == pytest.approx(
        menu_box["x"] + menu_box["width"] / 2, abs=0.5
    )
    assert line_box["y"] + line_box["height"] / 2 == pytest.approx(
        menu_box["y"] + menu_box["height"] / 2, abs=0.5
    )

    menu.click()
    blog_link = mobile_page.get_by_role(
        "navigation", name="Primary navigation"
    ).get_by_role("link", name="Blog", exact=True)
    expect(blog_link).to_be_visible()
    assert (
        blog_link.evaluate("element => getComputedStyle(element).justifyContent")
        == "center"
    )
