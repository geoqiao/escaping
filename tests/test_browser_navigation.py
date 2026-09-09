from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any, Literal
from urllib.parse import parse_qs, urlsplit

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
    Route,
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
from escaping.utils.html_sanitizer import sanitize_html  # noqa: E402

_ROOT = Path(__file__).parent.parent.absolute()
_THEMES = ("Quiet", "independent")
_MERMAID_RENDER_TIMEOUT_MS = 15_000
_ADJACENT_POSTS: tuple[tuple[int, str, str, datetime, str], ...] = (
    (4, "Tie low", "tie-low", datetime(2026, 1, 2, tzinfo=UTC), "focus"),
    (1, "Oldest post", "oldest", datetime(2026, 1, 1, tzinfo=UTC), "focus"),
    (11, "Newest post", "newest", datetime(2026, 1, 3, tzinfo=UTC), "focus"),
    (12, "Older post", "older", datetime(2026, 1, 1, tzinfo=UTC), "other"),
    (7, "Tie <high> & safe", "tie-high", datetime(2026, 1, 2, tzinfo=UTC), "other"),
)


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
                        {"name": "Home", "url": "/"},
                        {"name": "Blog", "url": "/blog/"},
                        {"name": "Projects", "url": "/projects/"},
                        {"name": "Tags", "url": "/tags/"},
                        {"name": "About", "url": "/about/"},
                        {"name": "RSS", "url": "/atom.xml"},
                    ]
                },
            },
            "profile": {"avatar": "/templates/Quiet/static/images/favicon.png"}
            if theme == "Quiet"
            else {},
            "about": {"issue_number": 10},
            "projects": [
                {
                    "repository": f"example/tool{i}",
                    "title": f"Tool {i}",
                    "summary": "A useful, independently maintained tool.",
                    "featured": i != 0,
                    "order": 6 - i,
                    "image": "/templates/Quiet/static/images/favicon.png"
                    if i == 6
                    else "",
                    "links": [
                        {"name": "Docs & examples", "url": "https://example.com/docs"}
                    ]
                    if i == 6
                    else [],
                    "fallback_metadata": {"stars": 100 - i, "language": "Python"},
                }
                for i in range(7)
            ]
            if theme == "Quiet"
            else [],
            "paths": {"page_size": 2},
            "security": {"token_env": "TEST_TOKEN"},
            "comments": {"enabled": True},
            "theme": {
                "source": "local",
                "name": "independent",
                "path": "tests/fixtures/independent_theme",
            }
            if theme == "independent"
            else {"source": "builtin", "name": theme},
        }
    )


def _adjacent_snapshot(
    number: int,
    title: str,
    slug: str,
    created_at: datetime,
    tag_name: str,
) -> IssueSnapshot:
    created_date = created_at.date().isoformat()
    return IssueSnapshot(
        number=number,
        title=title,
        author="geoqiao",
        body=(
            "---\n"
            f"slug: {slug}\n"
            "description: Description.\n"
            f'created_date: "{created_date}"\n'
            "---\n\nBody."
        ),
        labels=("type:blog", "published", f"tag:{tag_name}"),
        created_at=created_at,
        updated_at=created_at,
        is_pull_request=False,
    )


def _write_quiet_adjacent_site(output_dir: Path) -> None:
    settings = _browser_settings("Quiet")
    routes = RouteRegistry(str(settings.site.url))
    build_time = datetime(2026, 1, 20, tzinfo=UTC)
    content = ContentCompiler(settings, route_registry=routes).compile(
        [
            *(_adjacent_snapshot(*definition) for definition in _ADJACENT_POSTS),
            IssueSnapshot(
                number=2,
                title="Idea",
                author="geoqiao",
                body='---\ndescription: Idea.\ncreated_date: "2026-01-02"\n---\n\nIdea.',
                labels=("type:idea", "published"),
                created_at=build_time,
                updated_at=build_time,
                is_pull_request=False,
            ),
            IssueSnapshot(
                number=10,
                title="About",
                author="geoqiao",
                body='---\ndescription: About.\ncreated_date: "2026-01-03"\n---\n\nAbout.',
                labels=("type:about", "published"),
                created_at=build_time,
                updated_at=build_time,
                is_pull_request=False,
            ),
        ]
    )
    assert not content.has_errors
    site = SiteBuilder(settings, route_registry=routes).build(
        content,
        ProjectCompiler().compile(settings.projects, route=routes.projects()),
        build_start_time=build_time,
    )
    assert not site.has_errors
    renderer = RenderService(ThemeLoader(_ROOT).load(settings.theme))
    renderer.copy_theme_assets(output_dir)
    for output_path, html in renderer.render_site(site).items():
        path = output_dir / output_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")


@pytest.mark.parametrize("width", [1440, 390, 320])
def test_quiet_search_is_lazy_keyboard_usable_and_finds_public_content(
    comments_browser: Browser, site_servers: dict[str, str], width: int
) -> None:
    page = comments_browser.new_page(viewport={"width": width, "height": 844})
    requests: list[str] = []
    page.on("request", lambda request: requests.append(request.url))
    origin = site_servers["Quiet"]
    try:
        page.goto(origin)
        trigger = page.get_by_role("button", name="Search")
        if width < 768:
            page.get_by_role("button", name="Toggle menu").click()
        expect(trigger).to_be_visible()
        assert f"{origin}/search.json" not in requests
        trigger.click()
        dialog = page.get_by_role("dialog", name="Search")
        query = dialog.get_by_role("searchbox")
        expect(query).to_be_focused()
        query.fill("最终选择")
        results = dialog.locator(".search-results a")
        expect(results).to_have_count(1)
        expect(results.first).to_have_attribute("href", "/blog/a-blog/")
        query.fill("PI")
        expect(results).to_have_count(1)
        query.fill("tool 6")
        expect(results).to_have_count(1)
        expect(results.first).to_have_attribute(
            "href", "https://github.com/example/tool6"
        )
        query.fill("no-such-keyword")
        expect(dialog.get_by_role("status")).to_contain_text("No results")
        query.fill("最终选择")
        # A populated searchbox must not consume Escape just to clear its value.
        query.press("Escape")
        expect(dialog).not_to_be_visible()
        if width < 768:
            expect(page.get_by_role("button", name="Toggle menu")).to_be_focused()
        else:
            expect(trigger).to_be_focused()
        page.keyboard.press("Control+k")
        expect(query).to_be_focused()
        query.press("ArrowDown")
        expect(results.first).to_be_focused()
        page.keyboard.press("Escape")
        expect(dialog).not_to_be_visible()
        # Existing navigation dismisses when focus leaves it for the modal.
        if width < 768:
            expect(page.get_by_role("button", name="Toggle menu")).to_be_focused()
        else:
            expect(trigger).to_be_focused()
        page.keyboard.press("Control+k")
        expect(query).to_be_focused()
        assert requests.count(f"{origin}/search.json") == 1
        assert page.evaluate("document.documentElement.scrollWidth") == width
        # Native dialog keeps keyboard focus inside; Shift+Tab cannot reach the site.
        query.press("Shift+Tab")
        assert dialog.evaluate("el => el.contains(document.activeElement)")
        results.first.click()
        expect(page).to_have_url(f"{origin}/blog/a-blog/")
    finally:
        page.close()


@pytest.mark.parametrize("failure", ["http", "invalid", "unsafe"])
def test_quiet_search_failure_can_retry_without_rendering_untrusted_html(
    comments_browser: Browser, site_servers: dict[str, str], failure: str
) -> None:
    page = comments_browser.new_page()
    origin = site_servers["Quiet"]
    try:
        page.route(
            "**/search.json",
            lambda route: route.fulfill(
                status=503 if failure == "http" else 200,
                content_type="application/json",
                body="invalid json"
                if failure != "unsafe"
                else json.dumps(
                    {
                        "version": 1,
                        "items": [
                            {
                                "title": "<img src=x onerror=alert(1)>",
                                "description": "",
                                "tags": [],
                                "type": "Blog",
                                "url": "javascript:alert(1)",
                            }
                        ],
                    }
                ),
            ),
        )
        page.goto(origin)
        page.get_by_role("button", name="Search").click()
        dialog = page.get_by_role("dialog", name="Search")
        expect(dialog.get_by_role("status")).to_contain_text("Could not load")
        expect(dialog.locator("img")).to_have_count(0)
        expect(dialog.get_by_role("link", name="Browse Blog")).to_have_attribute(
            "href", "/blog/"
        )
        page.unroute("**/search.json")
        dialog.get_by_role("button", name="Retry").click()
        expect(dialog.get_by_role("status")).to_contain_text("Browse recent")
        dialog.get_by_role("searchbox").fill("unfinished")
        expect(dialog.locator(".search-results a")).to_have_count(1)
        expect(dialog.locator(".search-results a")).to_have_attribute(
            "href", "/ideas/2/"
        )
    finally:
        page.close()


@pytest.mark.parametrize("empty", [False, True])
def test_quiet_search_ranks_plain_text_safely_and_handles_an_empty_site(
    comments_browser: Browser, site_servers: dict[str, str], empty: bool
) -> None:
    page = comments_browser.new_page()
    title = '中文 Python <img src=x onerror="alert(1)">'
    items = [
        {
            "title": "Description match",
            "description": "中文 Python",
            "tags": [],
            "type": "Blog",
            "url": "/blog/a-blog/",
        },
        {
            "title": title,
            "description": "Safe <button> text.",
            "tags": [],
            "type": "Project",
            "url": "https://github.com/example/tool6",
        },
        {
            "title": "Tag match",
            "description": "",
            "tags": ["中文", "Python"],
            "type": "Idea",
            "url": "/ideas/2/",
        },
    ]
    try:
        page.route(
            "**/search.json",
            lambda route: route.fulfill(
                content_type="application/json",
                body=json.dumps({"version": 1, "items": [] if empty else items}),
            ),
        )
        page.goto(site_servers["Quiet"])
        page.get_by_role("button", name="Search").click()
        dialog = page.get_by_role("dialog", name="Search")
        if empty:
            expect(dialog.get_by_role("status")).to_contain_text("No published content")
        else:
            dialog.get_by_role("searchbox").fill("中文 PYTHON")
            expect(dialog.locator(".search-result-title")).to_have_text(
                [
                    title,
                    "Tag match",
                    "Description match",
                ]
            )
            expect(
                dialog.locator(".search-results img, .search-results button")
            ).to_have_count(0)
            page.emulate_media(media="print")
            expect(dialog).not_to_be_visible()
            expect(page.locator("main h1")).to_be_visible()
            expect(page.get_by_role("button", name="Search")).not_to_be_visible()
    finally:
        page.close()


@pytest.mark.parametrize("mode", ["no-js", "missing-script"])
def test_quiet_search_degrades_to_existing_navigation(
    comments_browser: Browser, site_servers: dict[str, str], mode: str
) -> None:
    page = comments_browser.new_page(java_script_enabled=mode != "no-js")
    try:
        if mode == "missing-script":
            page.route("**/search.js", lambda route: route.abort())
        page.goto(site_servers["Quiet"])
        expect(page.get_by_role("button", name="Search")).not_to_be_visible()
        expect(
            page.locator("#site-navigation").get_by_role(
                "link", name="Blog", exact=True
            )
        ).to_be_visible()
        expect(
            page.locator("#site-navigation").get_by_role(
                "link", name="Tags", exact=True
            )
        ).to_be_visible()
    finally:
        page.close()


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
    quiet_toc_snapshots = []
    for number, slug, body in (
        (
            21,
            "toc-headings",
            "Introduction.\n\n## Repeat\n\nText.\n\n## Repeat\n\n### 嵌套细节",
        ),
        (
            24,
            "toc-long",
            "\n\n".join(f"## Section {i}\n\n{long_paragraph}" for i in range(30)),
        ),
        (
            25,
            "syntax",
            '```python\n# Keep source intact\nimport os\nprint("hello")\n'
            + "# "
            + "x" * 180
            + "\n```\n\n```unknown-language\n<plain> & text\n```\n\n```\nunmarked text\n```",
        ),
        (22, "toc-none", "No section headings here."),
        (23, "toc-escaped", "Only code.\n\n```html\n<h2>Not a heading</h2>\n```"),
    ):
        snapshot = _adjacent_snapshot(
            number, "TOC sample", slug, datetime(2025, 1, 1, tzinfo=UTC), "toc"
        )
        quiet_toc_snapshots.append(
            replace(snapshot, body=snapshot.body.replace("Body.", body))
        )
    output_dirs: dict[str, Path] = {}
    for theme in _THEMES:
        settings = _browser_settings(theme)
        routes = RouteRegistry(str(settings.site.url))
        content = ContentCompiler(settings, route_registry=routes).compile(
            snapshots + (quiet_toc_snapshots if theme == "Quiet" else [])
        )
        site = SiteBuilder(settings, route_registry=routes).build(
            content,
            ProjectCompiler().compile(settings.projects, route=routes.projects()),
            build_start_time=build_time,
        )
        assert not site.has_errors

        renderer = RenderService(ThemeLoader(_ROOT).load(settings.theme))
        for variant in (theme, f"{theme}-disabled"):
            if variant.endswith("-disabled"):
                disabled = settings.model_copy(
                    update={
                        "comments": settings.comments.model_copy(
                            update={"enabled": False}
                        ),
                        "site": settings.site.model_copy(
                            update={
                                "navigation": settings.site.navigation.model_copy(
                                    update={"items": []}
                                )
                            }
                        ),
                    }
                )
                site = SiteBuilder(disabled, routes).build(
                    content,
                    ProjectCompiler().compile(
                        settings.projects, route=routes.projects()
                    ),
                    build_start_time=build_time,
                )
            output_dir = tmp_path_factory.mktemp(f"browser-site-{variant}")
            renderer.copy_theme_assets(output_dir)
            for output_path, html in renderer.render_site(site).items():
                path = output_dir / output_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(html, encoding="utf-8")
            output_dirs[variant] = output_dir
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
    return site_servers["Quiet"]


def test_quiet_blog_adjacent_navigation_is_http_keyboard_and_narrow_safe(
    browser: Browser, tmp_path: Path
) -> None:
    output_dir = tmp_path / "quiet-adjacent-site"
    output_dir.mkdir()
    _write_quiet_adjacent_site(output_dir)

    handler = partial(SimpleHTTPRequestHandler, directory=str(output_dir))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    context = browser.new_context(
        java_script_enabled=False, viewport={"width": 390, "height": 844}
    )
    page = context.new_page()
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        page.goto(f"{origin}/blog/tie-low/", wait_until="load")
        navigation = page.get_by_role("navigation", name="Article navigation")
        expect(navigation).to_be_visible()
        previous = navigation.get_by_role(
            "link", name=re.compile(r"^Previous: Tie <high> & safe$")
        )
        next_link = navigation.get_by_role("link", name="Next: Older post")
        expect(previous).to_be_visible()
        expect(next_link).to_be_visible()
        previous.focus()
        expect(previous).to_be_focused()
        page.keyboard.press("Tab")
        expect(next_link).to_be_focused()
        page.keyboard.press("Shift+Tab")
        expect(previous).to_be_focused()
        page.keyboard.press("Enter")
        expect(page).to_have_url(re.compile(r"/blog/tie-high/$"))
        expect(
            page.get_by_role("heading", name="Tie <high> & safe", exact=True)
        ).to_be_visible()

        page.goto(f"{origin}/blog/tie-low/", wait_until="load")
        navigation.get_by_role("link", name="Next: Older post").click()
        expect(page).to_have_url(re.compile(r"/blog/older/$"))
        expect(
            page.get_by_role("heading", name="Older post", exact=True)
        ).to_be_visible()

        page.goto(f"{origin}/blog/newest/", wait_until="load")
        navigation = page.get_by_role("navigation", name="Article navigation")
        expect(
            navigation.get_by_role("link", name=re.compile(r"^Previous:"))
        ).to_have_count(0)
        only_next = navigation.get_by_role("link", name="Next: Tie <high> & safe")
        expect(only_next).to_be_visible()
        bounds = only_next.bounding_box()
        navigation_bounds = navigation.bounding_box()
        viewport = page.viewport_size
        assert (
            bounds is not None
            and navigation_bounds is not None
            and viewport is not None
        )
        assert bounds["x"] > navigation_bounds["x"] + navigation_bounds["width"] / 2
        assert (
            navigation_bounds["x"] + navigation_bounds["width"] <= viewport["width"] + 1
        )

        page.goto(f"{origin}/blog/oldest/", wait_until="load")
        navigation = page.get_by_role("navigation", name="Article navigation")
        only_previous = navigation.get_by_role("link", name="Previous: Older post")
        expect(only_previous).to_be_visible()
        expect(
            navigation.get_by_role("link", name=re.compile(r"^Next:"))
        ).to_have_count(0)
        previous_bounds = only_previous.bounding_box()
        navigation_bounds = navigation.bounding_box()
        assert previous_bounds is not None and navigation_bounds is not None
        assert (
            previous_bounds["x"]
            < navigation_bounds["x"] + navigation_bounds["width"] / 2
        )
    finally:
        context.close()
        server.shutdown()
        server_thread.join()
        server.server_close()


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


def test_sanitized_fragments_stay_inside_the_theme_body(browser: Browser) -> None:
    page = browser.new_page()
    page.route("**/*", lambda route: route.abort())
    try:
        for fragment in (
            "<div><li><div><li>x</li></div></li></div>",
            "</div></article>KEEP",
            "<p><div>nested block</div></p>",
            "<table><div>foster</div><tr><td>cell</td></tr></table>",
            '<img src=x onerror="window.__injected=1"><script>window.__injected=1</script>',
        ):
            page.set_content(
                '<main id="theme"><div id="body">'
                + sanitize_html(fragment)
                + '<span id="tail">TAIL</span></div><footer id="footer">FOOTER</footer></main>'
            )
            assert page.evaluate("""() => ({
                tailInBody: document.getElementById('body').contains(document.getElementById('tail')),
                footerParent: document.getElementById('footer').parentElement.id,
                liveScripts: document.querySelectorAll('script').length,
                eventAttributes: [...document.querySelectorAll('*')].flatMap(el => [...el.attributes]).filter(a => /^on/i.test(a.name)).length,
                injected: !!window.__injected,
            })""") == {
                "tailInBody": True,
                "footerParent": "theme",
                "liveScripts": 0,
                "eventAttributes": 0,
                "injected": False,
            }, fragment
    finally:
        page.close()


def test_quiet_mobile_navigation_is_keyboard_operable(
    mobile_page: Page,
    site_server: str,
) -> None:
    page, origin = mobile_page, site_server
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
    page.keyboard.press("Space")
    expect(menu_control).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("Tab")
    expect(menu.get_by_role("button", name="Search")).to_be_focused()
    page.keyboard.press("Tab")
    expect(menu.locator("a").first).to_be_focused()
    page.keyboard.press("Tab")
    expect(blog_link).to_be_focused()
    page.keyboard.press("Enter")
    expect(page).to_have_url(origin + "/blog/")


@pytest.mark.parametrize("javascript", [True, False])
def test_independent_theme_keyboard_navigation_and_local_overflow(
    browser: Browser, site_servers: dict[str, str], javascript: bool
) -> None:
    tab = "Alt+Tab" if browser.browser_type.name == "webkit" else "Tab"
    page = browser.new_page(
        java_script_enabled=javascript, viewport={"width": 320, "height": 844}
    )
    page.route("https://**/*", lambda route: route.abort())
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    origin = site_servers["independent"]
    try:
        page.goto(origin + "/", wait_until="load")
        page.keyboard.press(tab)
        expect(page.locator(".skip-link")).to_be_focused()
        page.keyboard.press("Enter")
        expect(page.locator("#main-content")).to_be_focused()
        brand = page.locator(".brand")
        brand.focus()
        for link in page.locator(".primary-nav a").all():
            page.keyboard.press(tab)
            expect(link).to_be_focused()
            expect(link).to_be_in_viewport()
        brand.focus()
        page.keyboard.press(tab)
        page.keyboard.press(tab)
        page.keyboard.press("Enter")
        expect(page).to_have_url(origin + "/blog/")
        page.goto(origin + "/blog/a-blog/", wait_until="load")
        page.locator("#main-content").focus()
        region = page.locator(".rich-content")
        for _ in range(12):
            page.keyboard.press(tab)
            if region.evaluate("el => el === document.activeElement"):
                break
        expect(region).to_be_focused()
        assert region.evaluate("el => el.scrollWidth > el.clientWidth")
        region.evaluate("el => el.scrollLeft = 0")
        page.keyboard.press("ArrowRight", delay=100)
        expect(region).not_to_have_js_property("scrollLeft", 0)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")

        # Explicit [] keeps branding, but produces neither nav shell nor widget.
        empty = site_servers["independent-disabled"]
        page.goto(empty + "/blog/a-blog/", wait_until="load")
        expect(page.locator(".primary-nav, #comments-container, iframe")).to_have_count(
            0
        )
        assert page.locator("[data-theme-toggle]").is_visible() is javascript
        page.locator(".brand").focus()
        page.keyboard.press("Enter")
        expect(page).to_have_url(empty + "/")
        assert not errors
    finally:
        page.close()


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


def test_quiet_long_form_content_has_local_overflow_and_a_readable_width(
    mobile_page: Page,
    site_server: str,
) -> None:
    page = mobile_page
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


@pytest.mark.parametrize(
    "initialization", ["delayed-site", "blocked-site", "blocked-appearance"]
)
def test_quiet_navigation_is_stable_and_usable_when_initialization_is_unavailable(
    browser: Browser, site_servers: dict[str, str], initialization: str
) -> None:
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    pending: list[Route] = []
    failures: list[str] = []
    errors: list[str] = []
    page.on("requestfailed", lambda request: failures.append(request.url))
    page.on("pageerror", lambda error: errors.append(str(error)))
    script = "appearance.js" if initialization == "blocked-appearance" else "site.js"
    page.route(
        f"**/Quiet/static/js/{script}",
        lambda route: (
            pending.append(route) if initialization == "delayed-site" else route.abort()
        ),
    )
    try:
        page.goto(site_servers["Quiet"], wait_until="commit")
        surface = page.locator(".site-surface")
        expect(surface).to_be_visible()
        # WebKit's fonts.ready can wait for DOMContentLoaded, which is deliberately
        # held here. Observe rendered frames without waiting for initialization.
        page.evaluate(
            "new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
        )
        before = surface.bounding_box()
        assert before is not None
        menu = page.get_by_role("button", name="Toggle menu")
        navigation = page.get_by_role("navigation", name="Main navigation")
        blog = navigation.get_by_role("link", name="Blog", exact=False)
        if initialization == "blocked-appearance":
            expect(menu).to_be_hidden()
        else:
            # The control must work *before* the deferred script is available.
            expect(menu).to_be_visible()
            menu.focus()
            page.keyboard.press("Enter")
            expect(menu).to_have_attribute("aria-expanded", "true")
        expect(blog).to_be_visible()
        expect(navigation.locator('[aria-current="page"]')).to_have_attribute(
            "href", "/"
        )
        blog.focus()
        if initialization == "delayed-site":
            assert len(pending) == 1
            pending.pop().continue_()
            page.unroute(f"**/Quiet/static/js/{script}")
        page.wait_for_load_state("load")
        # Two rendered frames, not load-as-paint or a timing-dependent sleep.
        page.evaluate(
            "new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
        )
        after = surface.bounding_box()
        assert after is not None
        assert after["y"] == pytest.approx(before["y"], abs=1)
        expect(blog).to_be_focused()
        if initialization != "blocked-appearance":
            expect(menu).to_have_attribute("aria-expanded", "true")
            page.keyboard.press("Escape")
            expect(menu).to_have_attribute("aria-expanded", "false")
            expect(menu).to_be_focused()
            page.keyboard.press("Space")
            expect(blog).to_be_visible()
            blog.focus()
        page.keyboard.press("Enter")
        expect(page).to_have_url(re.compile(r"/blog/$"))
        expect(page.get_by_role("heading", name="Blog", exact=True)).to_be_visible()
        assert not errors
        if initialization.startswith("blocked"):
            assert any(url.endswith(script) for url in failures)
    finally:
        context.close()


@pytest.mark.parametrize(
    ("slug", "width", "wrap"),
    [
        ("toc-headings", 320, False),
        ("toc-headings", 390, False),
        ("toc-headings", 1160, False),
        ("toc-headings", 1161, False),
        ("toc-headings", 320, True),
        ("toc-none", 390, False),
        ("toc-escaped", 390, False),
    ],
)
def test_quiet_toc_reserves_its_natural_compact_size_before_initialization(
    browser: Browser, site_servers: dict[str, str], slug: str, width: int, wrap: bool
) -> None:
    context = browser.new_context(viewport={"width": width, "height": 900})
    page = context.new_page()
    pending: list[Route] = []
    page.route("**/Quiet/static/js/site.js", lambda route: pending.append(route))
    page.route("https://utteranc.es/**", lambda route: route.abort())
    try:
        page.goto(f"{site_servers['Quiet']}/blog/{slug}/", wait_until="commit")
        aside = page.locator(".reading-margin")
        summary = aside.locator("summary")
        # The whole article shell has arrived, but the deferred script has not.
        expect(aside).to_have_count(1)
        expect(page.locator(".post-content")).to_be_visible()
        if wrap:
            summary.evaluate(
                "e => { e.textContent = 'On this page — sections and subsections in this article'; }"
            )
        page.evaluate(
            "new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
        )
        main = page.locator(".reading-main")
        offset = "e => e.getBoundingClientRect().y - e.parentElement.getBoundingClientRect().y"
        before = main.evaluate(offset)
        height = aside.evaluate("e => e.getBoundingClientRect().height")
        has_headings = slug == "toc-headings"
        if has_headings and width <= 1160:
            assert height > 0
            gap = main.evaluate(
                "e => parseFloat(getComputedStyle(e.parentElement).rowGap)"
            )
            assert before == pytest.approx(height + gap)
        else:
            assert before == height == 0
        expect(summary).to_be_hidden()
        assert len(pending) == 1
        pending.pop().continue_()
        page.wait_for_load_state("load")
        page.evaluate(
            "new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
        )
        assert main.evaluate(offset) == pytest.approx(before, abs=1)
        if has_headings:
            expect(summary).to_be_visible()
            if width <= 1160:
                assert aside.evaluate("e => e.getBoundingClientRect().height") == height
                summary.press("Enter")
            else:
                expect(aside.locator("details")).to_have_attribute("open", "")
            assert aside.locator("a").evaluate_all(
                "links => links.map(a => a.getAttribute('href'))"
            ) == ["#repeat", "#repeat-section", "#%E5%B5%8C%E5%A5%97%E7%BB%86%E8%8A%82"]
            if width == 390:
                aside.get_by_role("link", name="嵌套细节").click()
                expect(page.get_by_role("heading", name="嵌套细节")).to_be_in_viewport()
                expect(page).to_have_url(
                    re.compile(r"#%E5%B5%8C%E5%A5%97%E7%BB%86%E8%8A%82$")
                )
        else:
            expect(summary).to_be_hidden()
            expect(aside.locator("a")).to_have_count(0)
    finally:
        context.close()


@pytest.mark.parametrize("javascript", [True, False], ids=["blocked-site", "js-off"])
def test_quiet_toc_unavailable_script_leaves_no_fake_control(
    browser: Browser, site_servers: dict[str, str], javascript: bool
) -> None:
    context = browser.new_context(
        java_script_enabled=javascript, viewport={"width": 320, "height": 700}
    )
    page = context.new_page()
    page.route("**/Quiet/static/js/site.js", lambda route: route.abort())
    page.route("https://utteranc.es/**", lambda route: route.abort())
    try:
        page.goto(f"{site_servers['Quiet']}/blog/toc-headings/", wait_until="load")
        aside = page.locator(".reading-margin")
        height = aside.evaluate("e => e.getBoundingClientRect().height")
        if javascript:
            # Natural closed summary + padding, not the height of an empty open nav.
            assert height == 60
        else:
            assert height == 0
        summary = aside.locator("summary")
        expect(summary).to_be_hidden()
        summary.focus()
        expect(summary).not_to_be_focused()
        expect(aside.locator("a")).to_have_count(0)
        expect(page.get_by_role("heading", name="Repeat").first).to_be_visible()
        expect(page.locator(".post-content")).to_contain_text("Introduction.")
        page.emulate_media(media="print")
        assert aside.evaluate("e => e.getBoundingClientRect().height") == 0
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
        # Safari pointer clicks do not focus buttons; test keyboard focus migration.
        toggle.focus()
        page.keyboard.press("Enter")
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")
        page.set_viewport_size({"width": 1440, "height": 900})
        expect(menu).to_have_attribute("aria-expanded", "false")
        expect(panel).to_be_visible()
        page.set_viewport_size({"width": viewport[0], "height": viewport[1]})
        expect(panel).to_be_hidden()
        expect(menu).to_be_focused()
    finally:
        page.close()


def test_quiet_navigation_and_appearance_controls_are_unboxed(
    browser: Browser, site_servers: dict[str, str]
) -> None:
    page = browser.new_page(
        viewport={"width": 1440, "height": 900}, color_scheme="light"
    )
    try:
        page.goto(site_servers["Quiet"], wait_until="load")
        current = page.locator('#site-navigation [aria-current="page"]')
        toggle = page.get_by_role("button", name="Dark mode")
        for mode in ("light", "dark"):
            expect(page.locator("html")).to_have_attribute("data-theme", mode)
            expect(current).to_have_css("background-color", "rgba(0, 0, 0, 0)")
            expect(current).to_have_css("font-weight", "600")
            expect(toggle).to_have_css("border-top-width", "0px")
            bounds = toggle.bounding_box()
            assert bounds is not None and bounds["height"] >= 44
            toggle.hover()
            expect(toggle).to_have_css("background-color", "rgba(0, 0, 0, 0)")
            page.keyboard.press("Tab")
            toggle.focus()
            expect(toggle).to_have_css("outline-style", "solid")
            toggle.click()
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


@pytest.fixture(scope="session", params=["chromium", "webkit"])
def comments_browser(
    request: pytest.FixtureRequest, browser: Browser, playwright_api: Playwright
) -> Iterator[Browser]:
    if request.param == "chromium":
        yield browser
        return
    try:
        engine = playwright_api.webkit.launch()
    except Error as exc:
        if os.environ.get("CI", "").lower() == "true":
            raise
        pytest.skip(f"Optional WebKit unavailable: {exc}")
    try:
        yield engine
    finally:
        engine.close()


def _replay_comments(page: Page, origin: str, mode: str = "success") -> list[str]:
    """Replay the investigation's official assets, never the public service.

    Only the GitHub HTTP response is synthetic. A blank frame is used solely
    as a postMessage peer, not as a replacement comments implementation.
    """
    assets = _ROOT / "tests/fixtures/utterances"
    resources = {
        "/client.js": ("utterances-client.js", "application/javascript"),
        "/utterances.html": ("utterances.html", "text/html"),
        "/utterances.6ec01640.js": ("utterances-app.js", "application/javascript"),
        "/stylesheets/themes/github-light/utterances.css": (
            "github-light.css",
            "text/css",
        ),
        "/stylesheets/themes/photon-dark/utterances.css": (
            "photon-dark.css",
            "text/css",
        ),
    }
    issue_requests: list[str] = []

    def respond(route: Route) -> None:
        request = route.request
        url = urlsplit(request.url)
        assert request.method == "GET", request.url
        assert "authorization" not in request.headers
        if request.url.startswith(origin + "/"):
            route.continue_()
            return
        if url.netloc == "utteranc.es" and url.path in resources:
            if mode == "blocked-client" and url.path == "/client.js":
                route.abort()
                return
            if mode == "peer" and url.path == "/utterances.html":
                route.fulfill(
                    content_type="text/html",
                    body="<!doctype html><title>Message peer</title>",
                )
                return
            filename, content_type = resources[url.path]
            route.fulfill(path=assets / filename, content_type=content_type)
            return
        if url.netloc == "api.github.com":
            issue_requests.append(request.url)
            assert re.fullmatch(r"/repos/geoqiao/site/issues/(1|2|10)", url.path), (
                request.url
            )
            assert not url.query
            number = int(url.path.rsplit("/", 1)[1])
            headers = {"access-control-allow-origin": "*"}
            if mode == "rate403":
                headers.update(
                    {
                        "x-ratelimit-limit": "60",
                        "x-ratelimit-remaining": "0",
                        "x-ratelimit-reset": "0",
                        "access-control-expose-headers": "X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset",
                    }
                )
                body = {"message": "API rate limit exceeded for controlled test client"}
            else:
                body = {
                    "number": number,
                    "comments": 0,
                    "locked": False,
                    "html_url": f"https://github.com/geoqiao/site/issues/{number}",
                }
            route.fulfill(
                status=403 if mode == "rate403" else 200,
                body=json.dumps(body),
                content_type="application/json",
                headers=headers,
            )
            return
        # No unexpected dependency, OAuth, avatar, search or write may go live.
        route.abort()
        pytest.fail(f"Unexpected external request: {request.url}")

    page.context.route("**/*", respond)
    return issue_requests


def _expect_comments_ready(page: Page, number: int) -> None:
    iframe = page.locator("#comments-container iframe")
    expect(iframe).to_have_count(1)
    expect(iframe).to_be_visible()
    bounds = iframe.bounding_box()
    assert bounds is not None and bounds["height"] > 0
    assert iframe.get_attribute("loading") is None
    thread = page.frame_locator("#comments-container iframe")
    login = thread.get_by_role("link", name="Sign in with GitHub")
    expect(login).to_be_visible()
    iframe.scroll_into_view_if_needed()
    expect(login).to_be_in_viewport()
    expect(login).to_have_attribute(
        "href", re.compile(r"^https://api\.utteranc\.es/authorize\?")
    )
    expect(thread.get_by_role("textbox", name="comment", exact=True)).to_be_disabled()
    expect(thread.get_by_role("link", name="0 Comments", exact=True)).to_have_attribute(
        "href", f"https://github.com/geoqiao/site/issues/{number}"
    )
    expect(page.locator(".comments-loading")).to_be_hidden()
    expect(page.locator("#comments-container .comments-error")).to_have_count(0)


@pytest.mark.parametrize("theme", _THEMES)
def test_comments_generated_theme_wiring_uses_issue_identity(
    browser: Browser, site_servers: dict[str, str], theme: str
) -> None:
    page = browser.new_page(color_scheme="light")
    origin = site_servers[theme]
    requests = _replay_comments(page, origin)
    try:
        # Each real template caller is wired, without multiplying protocol cases.
        for path, number in (("blog/a-blog/", 1), ("ideas/2/", 2), ("about/", 10)):
            page.goto(f"{origin}/{path}", wait_until="load")
            if number == 1:
                _expect_comments_ready(page, number)
            iframe = page.locator("#comments-container iframe")
            expect(iframe).to_have_count(1)
            query = parse_qs(urlsplit(iframe.get_attribute("src") or "").query)
            assert query["issue-number"] == [str(number)]
            assert query["repo"] == ["geoqiao/site"]
            assert "issue-term" not in query and "session" not in query
        assert requests == [
            f"https://api.github.com/repos/geoqiao/site/issues/{n}" for n in (1, 2, 10)
        ]
    finally:
        page.close()


@pytest.mark.parametrize("theme", _THEMES)
def test_disabled_comments_make_no_third_party_requests(
    comments_browser: Browser, site_servers: dict[str, str], theme: str
) -> None:
    page = comments_browser.new_page(viewport={"width": 390, "height": 844})
    origin = site_servers[f"{theme}-disabled"]
    external: list[str] = []
    page.on(
        "request",
        lambda request: (
            external.append(request.url)
            if not request.url.startswith(origin + "/")
            else None
        ),
    )
    page.route("https://**/*", lambda route: route.abort())
    try:
        for path in ("blog/a-blog/", "ideas/2/", "about/"):
            page.goto(f"{origin}/{path}", wait_until="networkidle")
            expect(
                page.locator("iframe, #comments-container, .comments-loading")
            ).to_have_count(0)
            expect(page.locator('a[href="#comments-title"]')).to_have_count(0)
            expect(page.locator(".post-content, .rich-content")).to_be_visible()
        assert not external
    finally:
        page.close()


@pytest.mark.parametrize("theme", _THEMES)
@pytest.mark.parametrize("javascript", [True, False])
def test_empty_menu_preserves_keyboard_entry_brand_and_appearance(
    browser: Browser, site_servers: dict[str, str], theme: str, javascript: bool
) -> None:
    page = browser.new_page(
        viewport={"width": 320, "height": 700}, java_script_enabled=javascript
    )
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    origin = site_servers[f"{theme}-disabled"]
    try:
        page.goto(f"{origin}/blog/a-blog/", wait_until="load")
        expect(page.get_by_role("button", name="Toggle menu")).to_have_count(0)
        page.keyboard.press("Tab")
        expect(page.get_by_role("link", name="Skip to main content")).to_be_focused()
        page.keyboard.press("Enter")
        expect(page.locator("#main-content")).to_be_focused()
        brand = page.locator(".identity, .brand")
        brand.focus()
        page.keyboard.press("Enter")
        expect(page).to_have_url(origin + "/")
        if not javascript:
            expect(page.locator(".theme-toggle:visible")).to_have_count(0)
            # A nonempty menu must not expose an inoperable appearance button either.
            page.goto(site_servers[theme] + "/", wait_until="load")
            expect(page.locator(".theme-toggle:visible")).to_have_count(0)
        else:
            toggle = page.locator(".theme-toggle")
            toggle.focus()
            expect(toggle).to_be_focused()
            page.keyboard.press("Enter")
            expect(page.locator("html")).to_have_attribute("data-theme", "dark")
        page.set_viewport_size({"width": 1440, "height": 900})
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert not errors
    finally:
        page.close()


def test_comments_success_syncs_theme_and_removes_late_lazy_frames(
    comments_browser: Browser, site_servers: dict[str, str]
) -> None:
    page = comments_browser.new_page(
        color_scheme="light", viewport={"width": 390, "height": 844}
    )
    origin = site_servers["Quiet"]
    _replay_comments(page, origin)
    page.clock.install()
    try:
        page.goto(f"{origin}/blog/a-blog/", wait_until="load")
        _expect_comments_ready(page, 1)
        frame = page.frame_locator("#comments-container iframe")
        for mode, stylesheet in (
            ("light", "github-light"),
            ("dark", "photon-dark"),
            ("light", "github-light"),
        ):
            # MutationObserver must react to the real root attribute, without reload.
            page.locator("html").evaluate(
                "(e, mode) => e.setAttribute('data-theme', mode)", mode
            )
            expect(frame.locator('link[rel="stylesheet"]')).to_have_attribute(
                "href", f"/stylesheets/themes/{stylesheet}/utterances.css"
            )
        page.clock.fast_forward(20_001)
        _expect_comments_ready(page, 1)
        # DOM insertion bypasses insertAdjacentHTML: exercise the observer too.
        page.locator("#comments-container").evaluate("""container => {
            const direct = document.createElement('iframe');
            direct.loading = 'lazy';
            direct.dataset.probe = 'direct';
            container.append(direct);
            const nested = document.createElement('div');
            const child = document.createElement('iframe');
            child.loading = 'lazy';
            child.dataset.probe = 'nested';
            nested.append(child);
            container.append(nested);
        }""")
        for probe in ("direct", "nested"):
            expect(page.locator(f'iframe[data-probe="{probe}"]')).not_to_have_attribute(
                "loading", "lazy"
            )
    finally:
        page.close()


@pytest.mark.parametrize("mode", ["rate403", "blocked-client"])
def test_comments_failure_has_bounded_keyboard_usable_issue_fallback(
    comments_browser: Browser, site_servers: dict[str, str], mode: str
) -> None:
    page = comments_browser.new_page()
    origin = site_servers["Quiet"]
    requests = _replay_comments(page, origin, mode)
    # Advance browser time through the *unaltered* production 20s watchdog.
    frozen = datetime(2026, 1, 1, tzinfo=UTC)
    page.clock.install(time=frozen)
    page.clock.pause_at(frozen)
    try:
        if mode == "rate403":
            with page.expect_event("pageerror") as error:
                page.goto(f"{origin}/blog/a-blog/", wait_until="load")
            assert "Error fetching issue via issue number." in str(error.value)
            iframe = page.locator("#comments-container iframe")
            expect(iframe).to_have_count(1)
            bounds = iframe.bounding_box()
            assert bounds is not None and bounds["height"] == 0
            expect(page.locator(".comments-loading")).to_be_visible()
            assert requests == ["https://api.github.com/repos/geoqiao/site/issues/1"]
        else:
            page.goto(f"{origin}/blog/a-blog/", wait_until="load")
            expect(page.locator("#comments-container iframe")).to_have_count(0)
            expect(
                page.locator("#comments-container .comments-error a")
            ).to_be_visible()
            assert not requests
        page.clock.fast_forward(20_001)
        error_message = page.locator("#comments-container .comments-error")
        expect(error_message).to_contain_text(
            "Your network or browser privacy settings may block third-party content."
        )
        expect(error_message).not_to_contain_text("Try turning off")
        fallback = error_message.get_by_role(
            "link", name="View or add comment on GitHub"
        )
        expect(fallback).to_be_visible()
        expect(fallback).to_have_attribute(
            "href", "https://github.com/geoqiao/site/issues/1"
        )
        expect(fallback).to_have_attribute("rel", "noopener")
        fallback.focus()
        expect(fallback).to_be_focused()
        # Follow the actual link without requesting GitHub or performing a write.
        page.context.route(
            "https://github.com/geoqiao/site/issues/1",
            lambda route: route.fulfill(
                content_type="text/html", body="<title>Original Issue</title>"
            ),
        )
        with page.expect_popup() as popup:
            page.keyboard.press("Enter")
        expect(popup.value).to_have_url("https://github.com/geoqiao/site/issues/1")
        popup.value.close()
        heading = page.get_by_role("heading", name="Opening Section", exact=True)
        heading.scroll_into_view_if_needed()
        expect(heading).to_be_in_viewport()
        expect(page.locator(".post-content")).to_contain_text("A blog post.")
    finally:
        page.close()


def test_comments_feedback_rejects_wrong_origin_and_source(
    comments_browser: Browser, site_servers: dict[str, str]
) -> None:
    page = comments_browser.new_page()
    origin = site_servers["Quiet"]
    _replay_comments(page, origin, "peer")
    frozen = datetime(2026, 1, 1, tzinfo=UTC)
    page.clock.install(time=frozen)
    page.clock.pause_at(frozen)
    try:
        page.goto(f"{origin}/blog/a-blog/", wait_until="load")
        iframe = page.locator("#comments-container iframe")
        handle = iframe.element_handle()
        assert handle is not None
        peer = handle.content_frame()
        assert peer is not None
        peer_url = peer.url
        # Real cross-window messages, not forged MessageEvent fields.
        page.evaluate("""() => {
            window.probeMessages = 0;
            addEventListener('message', () => window.probeMessages++);
        }""")
        # Same WindowProxy as the expected frame, but an untrusted origin.
        with page.expect_event(
            "framenavigated", predicate=lambda f: f.url == f"{origin}/robots.txt"
        ) as navigated:
            iframe.evaluate("(e, url) => { e.src = url; }", f"{origin}/robots.txt")
        peer = navigated.value
        peer.wait_for_load_state()
        for kind in ("resize", "error"):
            peer.evaluate(
                "(type) => parent.postMessage({type, height: 777}, '*')", kind
            )
        page.wait_for_function("window.probeMessages === 2")
        expect(page.locator(".comments-loading")).to_be_visible()
        expect(page.locator("#comments-container .comments-error")).to_have_count(0)
        with page.expect_event(
            "framenavigated", predicate=lambda f: f.url == peer_url
        ) as navigated:
            iframe.evaluate("(e, url) => { e.src = url; }", peer_url)
        peer = navigated.value
        peer.wait_for_load_state()
        # Correct origin, different WindowProxy (a sibling frame).
        page.evaluate(
            """url => {
            const sibling = document.createElement('iframe');
            sibling.id = 'untrusted-peer'; sibling.src = url;
            document.body.append(sibling);
        }""",
            peer_url,
        )
        sibling_handle = page.locator("#untrusted-peer").element_handle()
        assert sibling_handle is not None
        sibling = sibling_handle.content_frame()
        assert sibling is not None
        sibling.wait_for_url(peer_url)
        sibling.wait_for_load_state()
        for kind in ("resize", "error"):
            sibling.evaluate(
                "(type) => parent.postMessage({type, height: 777}, '*')", kind
            )
        page.wait_for_function("window.probeMessages === 4")
        # Shared feedback is source-checked; upstream client layout is origin-only
        # (see fixtures/utterances/README.md). Do not claim layout isolation here.
        expect(page.locator(".comments-loading")).to_be_visible()
        expect(page.locator("#comments-container .comments-error")).to_have_count(0)
        # The same error message from the actual trusted peer must be accepted.
        peer.evaluate("parent.postMessage({type: 'error'}, '*')")
        expect(page.locator("#comments-container .comments-error a")).to_be_visible()
        expect(page.locator("#comments-container .comments-error a")).to_have_attribute(
            "href", "https://github.com/geoqiao/site/issues/1"
        )
    finally:
        page.close()


@pytest.mark.parametrize("width", [1495, 1161, 1160, 390, 320])
def test_quiet_v3_centered_pages_and_compact_navigation(
    comments_browser: Browser, site_servers: dict[str, str], width: int
) -> None:
    page = comments_browser.new_page(viewport={"width": width, "height": 960})
    page.route("https://**/*", lambda route: route.abort())
    try:
        for path in (
            "",
            "blog/",
            "blog/page/2/",
            "tags/",
            "tags/pi/",
            "projects/",
            "about/",
            "blog/a-blog/",
            "ideas/2/",
        ):
            page.goto(f"{site_servers['Quiet']}/{path}", wait_until="load")
            page.evaluate("document.fonts.ready")
            geometry = page.locator("main").evaluate("""e => {
                const r = e.getBoundingClientRect();
                const rail = document.querySelector('.site-rail').getBoundingClientRect();
                const margin = document.querySelector('.reading-margin:not([hidden])')?.getBoundingClientRect();
                return {width: r.width, center: r.x + r.width / 2 - document.documentElement.clientWidth / 2,
                    rail: rail.width, gap: r.x - rail.right, toc: margin?.width,
                    rightGap: margin ? margin.left - r.right : null};
            }""")
            assert abs(geometry["center"]) < 1, (path, geometry)
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            ), path
            expect(
                page.locator("#site-navigation a:not([aria-current]) .nav-arrow")
            ).to_have_count(0)
            expect(
                page.locator("#site-navigation [aria-current] .nav-arrow")
            ).to_have_count(0 if path == "ideas/2/" else 1)
            if width > 1160:
                assert geometry["width"] == 704 and geometry["rail"] == 160
                assert geometry["gap"] == 40
                if geometry["toc"] is not None:
                    assert 160 <= geometry["toc"] <= 320 and geometry["rightGap"] == 40
            else:
                menu = page.get_by_role("button", name="Toggle menu")
                expect(menu).to_be_visible()
                menu.click()
                page.keyboard.press("Escape")
                expect(menu).to_be_focused()
                expect(menu).to_have_attribute("aria-expanded", "false")
            if page.locator(".post-content").count():
                expect(page.locator(".post-content")).to_have_css("font-size", "16px")
                expect(page.locator(".post-content")).to_have_css("line-height", "28px")
            if path == "blog/a-blog/":
                title = page.locator(".article-heading h1")
                expect(title).to_have_css("font-size", "24px")
                expect(title).to_have_css("line-height", "42px")
                expect(title).to_have_css("letter-spacing", "normal")
                expect(title).to_have_css("text-wrap", "wrap")
    finally:
        page.close()


def test_quiet_v3_toc_follows_page_when_taller_than_viewport(
    comments_browser: Browser, site_servers: dict[str, str]
) -> None:
    page = comments_browser.new_page(viewport={"width": 1495, "height": 520})
    page.route("https://**/*", lambda route: route.abort())
    try:
        page.goto(f"{site_servers['Quiet']}/blog/toc-long/", wait_until="load")
        margin, toc = page.locator(".reading-margin"), page.locator(".toc")
        expect(margin).to_have_css("position", "static")
        expect(toc.locator("nav")).to_have_css("overflow-y", "visible")
        assert toc.locator("nav").evaluate("e => e.scrollHeight <= e.clientHeight + 1")
        last = toc.locator("a").last
        last.focus()
        expect(last).to_be_in_viewport()
        page.keyboard.press("Enter")
        expect(
            page.get_by_role("heading", name="Section 29", exact=True)
        ).to_be_in_viewport()
        page.evaluate("scrollTo(0, 0)")
        toc.locator("summary").click()
        expect(margin).to_have_css("position", "sticky")
        toc.locator("summary").click()
        expect(margin).to_have_css("position", "static")
        page.set_viewport_size({"width": 1495, "height": 1800})
        expect(margin).to_have_css("position", "sticky")
        page.set_viewport_size({"width": 1495, "height": 520})
        expect(margin).to_have_css("position", "static")
    finally:
        page.close()


def test_quiet_v3_ordered_featured_cards_and_generic_about(
    comments_browser: Browser, site_servers: dict[str, str]
) -> None:
    page = comments_browser.new_page(viewport={"width": 1495, "height": 960})
    page.route("https://**/*", lambda route: route.abort())
    try:
        for path, count in (("", 4), ("about/", 4), ("projects/", 7)):
            page.goto(f"{site_servers['Quiet']}/{path}", wait_until="load")
            cards = page.locator(".work-card")
            expect(cards).to_have_count(count)
            assert cards.locator("h2").all_text_contents() == [
                f"Tool {i}" for i in range(6, 6 - count, -1)
            ]
            if path == "about/":
                expect(page.locator(".about-header img")).to_have_count(0)
                expect(page.locator("main img")).to_have_count(1)
                expect(page.locator(".more-projects")).to_have_css(
                    "border-width", "0px"
                )
                narrative_box = page.locator(".post-content").bounding_box()
                cards_box = cards.first.bounding_box()
                assert narrative_box is not None and cards_box is not None
                assert narrative_box["y"] < cards_box["y"]
                expect(page.locator(".post-content")).to_contain_text("Things I Do")
                assert page.locator(".about-story h2").evaluate(
                    "e => parseFloat(getComputedStyle(e).fontSize)"
                ) == pytest.approx(18.72, abs=0.01)
                expect(page.locator(".about-story > p").first).to_have_css(
                    "font-size", "20px"
                )
                expect(page.locator(".about-story > p").first).to_have_css(
                    "line-height", "35px"
                )
                expect(page.locator("#comments-container")).to_have_attribute(
                    "data-issue-number", "10"
                )
            else:
                box = cards.first.bounding_box()
                assert box is not None and box["width"] / box[
                    "height"
                ] == pytest.approx(1.618, abs=0.01)
            expect(cards.locator("img")).to_have_count(1)
            cards.first.locator("img").scroll_into_view_if_needed()
            expect(cards.first.locator("img")).to_have_js_property("complete", True)
            assert cards.first.locator("img").evaluate("e => e.naturalWidth > 0")
            expect(
                cards.first.get_by_role(
                    "link", name="Docs & examples", include_hidden=True
                )
            ).to_have_attribute("href", "https://example.com/docs")
            cards.locator(".work-summary").first.evaluate(
                "e => e.textContent = 'LongConfigurableText'.repeat(80)"
            )
            cards.locator(".work-footer a").first.evaluate(
                "e => e.textContent = 'https://example.com/' + 'DocumentationLink'.repeat(20)"
            )
            for width in (1495, 320):
                page.set_viewport_size({"width": width, "height": 960})
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                )
                assert cards.evaluate_all(
                    "els => els.every(e => e.scrollHeight <= e.clientHeight + 1)"
                )
            page.set_viewport_size({"width": 1495, "height": 960})
    finally:
        page.close()


def test_quiet_v3_code_surface_preserves_text_colors_and_native_scroll(
    comments_browser: Browser, site_servers: dict[str, str]
) -> None:
    page = comments_browser.new_page(
        viewport={"width": 1495, "height": 960}, color_scheme="light"
    )
    page.route("https://**/*", lambda route: route.abort())
    try:
        page.emulate_media(reduced_motion="reduce")
        page.goto(f"{site_servers['Quiet']}/blog/syntax/", wait_until="load")
        blocks = page.locator(".code-block")
        expect(blocks).to_have_count(3)
        assert blocks.locator(".code-language").all_text_contents() == [
            "python",
            "unknown-language",
            "text",
        ]
        code = blocks.first.locator("code")
        expected = (
            '# Keep source intact\nimport os\nprint("hello")\n# ' + "x" * 180 + "\n"
        )
        assert code.text_content() == expected
        assert code.locator("span").count() > 3
        assert blocks.nth(1).locator("code").text_content() == "<plain> & text\n"
        for width in (1495, 390, 320):
            page.set_viewport_size({"width": width, "height": 960})
            pre = blocks.first.locator("pre")
            expect(pre).to_have_css("white-space", "pre")
            expect(pre).to_have_css("scrollbar-width", "thin")
            assert "rgba(0, 0, 0, 0)" in pre.evaluate(
                "e => getComputedStyle(e).scrollbarColor"
            )
            assert pre.evaluate("e => e.scrollWidth > e.clientWidth")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            pre.focus()
            expect(pre).to_be_focused()
            if comments_browser.browser_type.name == "chromium":
                page.keyboard.press("ArrowRight")
                expect(pre).not_to_have_js_property("scrollLeft", 0)
            else:
                pre.hover()
                page.mouse.wheel(200, 0)
                expect(pre).not_to_have_js_property("scrollLeft", 0)
        for mode, background, top in (
            ("light", "rgb(246, 247, 249)", "rgb(238, 240, 243)"),
            ("dark", "rgb(27, 29, 34)", "rgb(32, 35, 41)"),
        ):
            page.locator("html").evaluate("(e, mode) => e.dataset.theme = mode", mode)
            expect(blocks.first).to_have_css("background-color", background)
            expect(blocks.first.locator(".code-tools")).to_have_css(
                "background-color", top
            )
            assert code.evaluate(
                "e => getComputedStyle(e).color === getComputedStyle(document.body).color"
            )
        page.evaluate(
            "Object.defineProperty(navigator, 'clipboard', {value: {writeText: text => {window.copied = text; return Promise.resolve();}}})"
        )
        blocks.first.locator(".copy-code").click()
        assert page.evaluate("window.copied") == expected
        expect(blocks.first.locator(".copy-code")).to_have_text("Copied")
        page.emulate_media(media="print")
        expect(blocks.first).to_have_css("background-color", "rgb(255, 255, 255)")
        assert code.locator("span").evaluate_all(
            "els => els.every(e => getComputedStyle(e).color === 'rgb(0, 0, 0)' && getComputedStyle(e).backgroundColor === 'rgba(0, 0, 0, 0)')"
        )
        page.emulate_media(media="screen")
        page.goto(f"{site_servers['Quiet']}/blog/a-blog/", wait_until="load")
        expect(page.locator("pre.mermaid svg")).to_have_count(
            1, timeout=_MERMAID_RENDER_TIMEOUT_MS
        )
        expect(
            page.locator(".code-block .mermaid, .code-block .language-mermaid")
        ).to_have_count(0)
    finally:
        page.close()
