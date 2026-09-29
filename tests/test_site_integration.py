"""SiteCompiler end-to-end tracers and the rendered-artifact validator."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from escaping.artifact_validation import SiteArtifactValidator
from escaping.build_result import BuildResult
from escaping.config import Settings
from escaping.models.issue_snapshot import IssueSnapshot
from escaping.models.site import SiteModel
from escaping.output_staging import OUTPUT_MARKER
from escaping.site_compiler import (
    SiteCompiler,
    check_theme,
    compile_site,
    prepare_theme,
    render_site,
)

_SITEMAP_LOC = "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
_ATOM_ID = "{http://www.w3.org/2005/Atom}entry/{http://www.w3.org/2005/Atom}id"
_UNICODE_TAG = "/tags/%E7%A4%BA%E4%BE%8B-%E6%A0%87%E7%AD%BE/"


def _settings(**overrides: object) -> Settings:
    return Settings.model_validate(
        {
            "github": {"repo": "geoqiao/site", "allowed_authors": ["geoqiao"]},
            "site": {
                "title": "geoqiao.me",
                "author": "geoqiao",
                "url": "https://geoqiao.me/",
                "description": "A strict personal site.",
            },
            "about": {"issue_number": 10},
            "comments": {"enabled": True},
            "projects": [{"repository": "geoqiao/escaping", "summary": "A compiler."}],
            **overrides,
        }
    )


def _snapshot(
    number: int,
    kind: str,
    body: str = "A **safe** body.",
    *,
    labels: tuple[str, ...] = (),
    title: str | None = None,
) -> IssueSnapshot:
    created = datetime(2026, 1, number, 12, tzinfo=UTC)
    return IssueSnapshot(
        number,
        title or f"{kind.title()} {number}",
        "geoqiao",
        body,
        (f"type:{kind}", "published", *labels),
        created,
        created,
        False,
    )


_CONTENT = (
    _snapshot(
        1,
        "blog",
        "---\nslug: hello\n---\n\nHello.",
        labels=("tag:Python", "tag:示例 标签"),
    ),
    _snapshot(5, "idea", "An idea."),
    _snapshot(10, "about", "About me."),
)


class _Issues:
    """An Issue source that records whether the build asked for Issues."""

    def __init__(self, snapshots: Sequence[IssueSnapshot]) -> None:
        self.snapshots = list(snapshots)
        self.calls = 0

    def __call__(self) -> list[IssueSnapshot]:
        self.calls += 1
        return self.snapshots


def _generate(
    root: Path, snapshots: Sequence[IssueSnapshot], settings: Settings | None = None
) -> tuple[BuildResult, _Issues]:
    issues = _Issues(snapshots)
    compiler = SiteCompiler(settings or _settings(), config_root=root, issues=issues)
    return compiler.generate(), issues


def _theme(
    root: Path, files: dict[str, str], manifest: str = "", where: str = "theme"
) -> str:
    """Write a local Theme next to the Config; returns its ``theme.use``."""
    theme = root / where
    theme.mkdir(parents=True)
    (theme / "theme.yaml").write_text(
        manifest or "api: 4\nextends: quiet\n", encoding="utf-8"
    )
    for name, text in files.items():
        (theme / name).write_text(text, encoding="utf-8")
    return f"./{where}"


def _sitemap(output: Path) -> list[str]:
    root = ET.fromstring((output / "sitemap.xml").read_bytes())  # noqa: S314
    return [loc.text or "" for loc in root.iter(_SITEMAP_LOC)]


def test_build_publishes_the_site_and_skips_only_broken_issues(
    tmp_path: Path,
) -> None:
    snapshots = [
        *_CONTENT,
        _snapshot(2, "blog", "---\nslug: hello\n---\n\nImpostor.", title="Impostor"),
        _snapshot(3, "idea", "---\nunknown: x\n---\n\nIdea."),
        _snapshot(4, "blog", "Bad tag.", labels=("tag:C++",)),
    ]

    result, _ = _generate(tmp_path, snapshots)

    assert result.success, result.diagnostics
    assert result.skipped_issues == (2, 3, 4)
    assert {
        (d.code, d.issue_number) for d in result.diagnostics if d.severity == "error"
    } == {
        ("SLUG_DUPLICATE", 2),
        ("FRONT_MATTER_UNKNOWN_FIELD", 3),
        ("TAG_INVALID", 4),
    }
    output = tmp_path / "output"
    for name in (
        OUTPUT_MARKER,
        "index.html",
        "blog/index.html",
        "blog/hello/index.html",
        "ideas/index.html",
        "ideas/5/index.html",
        "about/index.html",
        "projects/index.html",
        "tags/index.html",
        "tags/python/index.html",
        "tags/示例-标签/index.html",
        "404.html",
        "atom.xml",
        "robots.txt",
        "search.json",
        "assets/css/style.css",
        "assets/escaping/comments.js",
    ):
        assert (output / name).is_file(), name
    assert not (output / "ideas/3").exists()
    post = (output / "blog/hello/index.html").read_text(encoding="utf-8")
    assert "Hello." in post and "Impostor" not in post
    assert f'href="{_UNICODE_TAG}"' in post
    locs = _sitemap(output)
    assert locs[0] == "https://geoqiao.me/" and len(locs) == len(set(locs))
    assert f"https://geoqiao.me{_UNICODE_TAG}" in locs
    assert not [loc for loc in locs if loc.endswith((".xml", ".txt", ".json"))]
    feed = ET.fromstring((output / "atom.xml").read_bytes())  # noqa: S314
    assert [e.text for e in feed.findall(_ATOM_ID)] == [
        "https://geoqiao.me/blog/hello/"
    ]


def _unowned_output(root: Path) -> dict[str, Any]:
    (root / "output").mkdir()
    (root / "output" / "notes.md").write_text("mine", encoding="utf-8")
    return {}


def _theme_in_output(root: Path) -> dict[str, Any]:
    use = _theme(root, {}, where="public/theme")
    (root / "public" / OUTPUT_MARKER).write_text("", encoding="utf-8")
    return {"theme": {"use": use}, "paths": {"output": "public"}}


@pytest.mark.parametrize(
    ("prepare", "code", "problem"),
    [
        (
            lambda root: {"theme": {"use": "quiet", "options": {"taglin": "x"}}},
            "THEME_INVALID",
            "theme.options.taglin",
        ),
        (
            lambda root: {"theme": {"use": _theme(root, {}, "api: 4\n")}},
            "THEME_INVALID",
            "missing template blog.html",
        ),
        (lambda root: {"paths": {"output": ".."}}, "OUTPUT_UNSAFE", "(..)"),
        (_unowned_output, "OUTPUT_UNSAFE", "did not create"),
        (_theme_in_output, "OUTPUT_UNSAFE", "would delete the Theme"),
    ],
    ids=["option", "template", "outside", "unowned", "theme-in-output"],
)
def test_local_problems_fail_before_any_issue_is_read(
    tmp_path: Path,
    prepare: Callable[[Path], dict[str, Any]],
    code: str,
    problem: str,
) -> None:
    settings = _settings(**prepare(tmp_path))
    before = sorted(tmp_path.rglob("*"))

    result, issues = _generate(tmp_path, _CONTENT, settings)

    assert not result.success and issues.calls == 0
    assert {d.code for d in result.diagnostics} == {code}
    assert any(problem in d.message for d in result.diagnostics)
    assert sorted(tmp_path.rglob("*")) == before


def test_extra_pages_and_navigation_reach_the_output(tmp_path: Path) -> None:
    template = (
        '{% extends "base.html" %}{% block content %}'
        '<h1>{{ page.project.title if page.project else "Now" }}</h1>'
        "{% endblock %}"
    )
    use = _theme(tmp_path, {"now.html": template, "work.html": template})
    site = _settings().model_dump()["site"]
    site["navigation"] = {"items": [{"name": "Now", "url": "/now/"}]}
    settings = _settings(
        site=site,
        theme={"use": use},
        pages={
            "extra": [
                {"path": "/now/", "template": "now.html"},
                {
                    "path": "/work/{slug}/",
                    "template": "work.html",
                    "for_each": "projects",
                },
            ]
        },
        projects=[
            {"repository": "geoqiao/escaping"},
            {"website": "https://example.org/", "slug": "site", "title": "Site"},
        ],
    )

    result, _ = _generate(tmp_path, _CONTENT, settings)

    assert result.success, result.diagnostics
    output = tmp_path / "output"
    assert "<h1>Now</h1>" in (output / "now/index.html").read_text(encoding="utf-8")
    assert "<h1>Site</h1>" in (output / "work/site/index.html").read_text(
        encoding="utf-8"
    )
    projects = (output / "projects/index.html").read_text(encoding="utf-8")
    assert 'href="/work/escaping/"' in projects and 'href="/work/site/"' in projects
    assert 'href="/now/"' in (output / "blog/index.html").read_text(encoding="utf-8")
    assert {"https://geoqiao.me/now/", "https://geoqiao.me/work/site/"} <= set(
        _sitemap(output)
    )


def _rendered(root: Path) -> tuple[SiteModel, Path]:
    """A valid Quiet site rendered into ``root/candidate``."""
    settings = _settings()
    theme, options = prepare_theme(settings, root)
    site = compile_site(
        settings,
        _CONTENT,
        theme,
        project_enricher=None,
        build_start_time=datetime(2026, 1, 20, tzinfo=UTC),
    )
    assert not site.has_errors, site.diagnostics
    candidate = root / "candidate"
    candidate.mkdir()
    render_site(candidate, site, theme, options)
    assert SiteArtifactValidator(site).validate(candidate) == []
    return site, candidate


def _inject(page: Path, html: str) -> None:
    page.write_text(
        page.read_text(encoding="utf-8").replace("</body>", f"{html}</body>", 1),
        encoding="utf-8",
    )


def test_validator_requires_every_route_file_and_no_stray_pages(
    tmp_path: Path,
) -> None:
    site, candidate = _rendered(tmp_path)
    (candidate / "tags/python/index.html").unlink()
    (candidate / "atom.xml").rename(candidate / "ATOM.XML")
    (candidate / "drafts").mkdir()
    (candidate / "drafts/index.html").write_text("<p>Draft</p>", encoding="utf-8")
    # 404.html is served for any path, so its relative links start at the root.
    _inject(candidate / "404.html", '<a href="about/">About</a><img src="gone.png">')

    diagnostics = SiteArtifactValidator(site).validate(candidate)

    assert [(d.code, d.message) for d in diagnostics] == [
        ("MISSING_ROUTE", "missing page file: atom.xml"),
        ("MISSING_ROUTE", "missing page file: tags/python/index.html"),
        ("UNREGISTERED_HTML", "drafts/index.html is not a page of this site"),
        (
            "BROKEN_INTERNAL_LINK",
            "404.html: img points to /gone.png, which is not a page or file of "
            "this site",
        ),
    ]


@pytest.mark.parametrize(
    ("reference", "broken"),
    [
        ('<a href="/Blog/">', "/Blog/"),
        ('<a href="https://geoqiao.me/blog/missing/">', "/blog/missing/"),
        ('<a href="missing/">', "/blog/hello/missing/"),
        ('<img src="pic.png">', "/blog/hello/pic.png"),
        ('<link rel="stylesheet" href="/assets/css/missing.css">', "missing.css"),
        ('<script data-runtime-src="/assets/escaping/gone.js"></script>', "gone.js"),
        ('<img srcset="/assets/images/favicon.png 1x, /assets/b.png 2x">', "/b.png"),
        ('<meta property="og:image" content="https://geoqiao.me/og.png">', "og.png"),
        ('<a href="/">', None),
        ('<a href="https://geoqiao.me/blog/?page=2#top">', None),
        (f'<a href="{_UNICODE_TAG}">', None),
        ('<a href="/tags/示例-标签/">', None),
        ('<img src="/assets/images/favicon.png?v=1#icon">', None),
        ('<video src="/assets/demo.mp4">', "/assets/demo.mp4"),
        ('<video poster="/assets/demo.png">', "/assets/demo.png"),
        ('<iframe src="/tool/editor/">', "/tool/editor/"),
        ('<a href="https://example.org/missing/">', None),
        # A folder this site does not write may be a project site on the host.
        ('<a href="https://geoqiao.me/tool/">', None),
        ('<img src="//cdn.example.org/missing.png">', None),
        ('<a href="mailto:me@example.org">', None),
        ('<a href="#missing">', None),
    ],
)
def test_validator_resolves_each_reference_against_its_page(
    tmp_path: Path, reference: str, broken: str | None
) -> None:
    site, candidate = _rendered(tmp_path)
    _inject(candidate / "blog/hello/index.html", reference)

    diagnostics = SiteArtifactValidator(site).validate(candidate)

    if broken is None:
        assert diagnostics == []
    else:
        assert [d.code for d in diagnostics] == ["BROKEN_INTERNAL_LINK"]
        assert diagnostics[0].message.startswith("blog/hello/index.html: ")
        assert broken in diagnostics[0].message


@pytest.mark.parametrize(
    ("filename", "url_name", "status", "valid"),
    [
        ("encoded%20name.txt", "encoded%20name.txt", 404, False),
        ("encoded%20name.txt", "encoded%2520name.txt?download=1#file", 200, True),
        ("space name.txt", "space%20name.txt", 200, True),
        ("雪.txt", "%E9%9B%AA.txt", 200, True),
    ],
)
def test_file_urls_decode_once_like_local_http(
    filename: str, url_name: str, status: int, valid: bool, tmp_path: Path
) -> None:
    site, candidate = _rendered(tmp_path)
    asset = candidate / "assets" / filename
    asset.write_text("Asset sentinel.", encoding="utf-8")
    url = f"/assets/{url_name}"
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(candidate))
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        try:
            with urlopen(
                f"http://127.0.0.1:{server.server_port}{url}", timeout=5
            ) as response:
                actual_status = response.status
                assert response.read() == asset.read_bytes()
        except HTTPError as exc:
            actual_status = exc.code
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert actual_status == status
    _inject(candidate / "blog/hello/index.html", f'<a href="{url}"></a>')
    codes = [d.code for d in SiteArtifactValidator(site).validate(candidate)]
    assert codes == ([] if valid else ["BROKEN_INTERNAL_LINK"])


@pytest.mark.parametrize(
    ("filename", "url_name"),
    [
        ("bad%name.txt", "bad%name.txt"),
        ("bad%FFname.txt", "bad%FFname.txt"),
        ("bad%00name.txt", "bad%00name.txt"),
        ("nested%2fsecret.txt", "nested%2fsecret.txt"),
        ("nested%5csecret.txt", "nested%5csecret.txt"),
        ("%2e%2e/safe.txt", "%2e%2e/safe.txt"),
        ("safe.txt", "nested/../safe.txt"),
        ("ab.txt", "a\tb.txt"),
    ],
)
def test_unsafe_file_urls_fail_before_normalization(
    filename: str, url_name: str, tmp_path: Path
) -> None:
    site, candidate = _rendered(tmp_path)
    asset = candidate / "assets" / filename
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_text("Must not authorize an unsafe URL.", encoding="utf-8")
    page = candidate / "blog/hello/index.html"
    original = page.read_text(encoding="utf-8")
    for tag, attr in (("a", "href"), ("img", "src")):
        page.write_text(original, encoding="utf-8")
        _inject(page, f'<{tag} {attr}="/assets/{url_name}"></{tag}>')
        assert [d.code for d in SiteArtifactValidator(site).validate(candidate)] == [
            "INVALID_INTERNAL_PATH"
        ]


def test_a_symlinked_file_is_not_part_of_the_site(tmp_path: Path) -> None:
    site, candidate = _rendered(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("Outside the candidate.", encoding="utf-8")
    (candidate / "assets/escape.txt").symlink_to(outside)
    _inject(candidate / "blog/hello/index.html", '<a href="/assets/escape.txt"></a>')
    assert [d.code for d in SiteArtifactValidator(site).validate(candidate)] == [
        "BROKEN_INTERNAL_LINK"
    ]


def test_theme_check_reports_seo_gaps_as_warnings(tmp_path: Path) -> None:
    quiet = check_theme(_settings(), config_root=tmp_path)
    assert quiet.success and quiet.diagnostics == (), quiet.diagnostics

    use = _theme(
        tmp_path,
        {
            "ideas.html": "<!doctype html><html><head><title> </title>"
            '<meta property="og:url" content="https://geoqiao.me/wrong/">'
            "</head><body></body></html>"
        },
    )
    result = check_theme(_settings(theme={"use": use}), config_root=tmp_path)

    assert result.success
    assert [(d.severity, d.code) for d in result.diagnostics] == [
        ("warning", "SEO_TITLE"),
        ("warning", "SEO_DESCRIPTION"),
        ("warning", "SEO_CANONICAL"),
        ("warning", "SEO_URL"),
    ]
    assert all(d.message.startswith("ideas/index.html: ") for d in result.diagnostics)


def test_redirects_send_old_addresses_to_pages_of_the_site(tmp_path: Path) -> None:
    settings = _settings(
        redirects={
            "/blog/old-hello/": "/blog/older-hello/",  # follows the next one
            "/blog/older-hello/": "/blog/hello/",
            "/posts/%E4%BD%A0%E5%A5%BD.html": "/about/",
            "/blog/gone/": "/blog/missing/",
            "/blog/hello/": "/about/",
        }
    )

    result, _ = _generate(tmp_path, _CONTENT, settings)

    assert result.success, result.diagnostics
    assert [d.message for d in result.diagnostics if d.code == "REDIRECT_LEFT_OUT"] == [
        "redirects: /blog/gone/ points to /blog/missing/, which is not a page of "
        "this site; the redirect is left out",
        "redirects: /blog/hello/ is a page of this site now; the redirect is left out",
    ]
    output = tmp_path / "output"
    old = (output / "blog/old-hello/index.html").read_text(encoding="utf-8")
    assert '<link rel="canonical" href="https://geoqiao.me/blog/hello/">' in old
    assert (
        '<meta http-equiv="refresh" content="0; url=https://geoqiao.me/blog/hello/">'
        in old
    )
    assert '<meta name="robots" content="noindex">' in old
    assert (output / "blog/older-hello/index.html").read_text(encoding="utf-8") == old
    assert "https://geoqiao.me/about/" in (output / "posts/你好.html").read_text(
        encoding="utf-8"
    )
    assert "Hello." in (output / "blog/hello/index.html").read_text(encoding="utf-8")
    assert not (output / "blog/gone").exists()
    assert not any("old-hello" in url for url in _sitemap(output))


def test_a_blog_page_wins_over_a_redirect_and_can_be_its_target(
    tmp_path: Path,
) -> None:
    settings = _settings(
        paths={"page_size": 1},
        redirects={"/blog/page/2/": "/about/", "/old-archive/": "/blog/page/2/"},
    )
    content = (*_CONTENT, _snapshot(2, "blog", "---\nslug: second\n---\n\nTwo."))

    result, _ = _generate(tmp_path, content, settings)

    assert result.success, result.diagnostics
    output = tmp_path / "output"
    assert "http-equiv" not in (output / "blog/page/2/index.html").read_text(
        encoding="utf-8"
    )
    assert "https://geoqiao.me/blog/page/2/" in (
        output / "old-archive/index.html"
    ).read_text(encoding="utf-8")


_UNDER_A_PATH = {
    "title": "Notes",
    "author": "geoqiao",
    "url": "https://geoqiao.github.io/notes",
    "description": "A site under a path.",
}


def test_a_site_under_a_path_keeps_every_address_below_it(tmp_path: Path) -> None:
    settings = _settings(
        site=_UNDER_A_PATH,
        profile={"avatar": "/assets/images/favicon.png"},
        seo={"social_image": "/assets/images/favicon.png"},
        redirects={"/old-hello/": "/blog/hello/"},
    )
    body = (
        "---\nslug: hello\n---\n\n"
        "See [About](/about/), [elsewhere](https://example.com/) and "
        "![icon](/assets/images/favicon.png)."
    )
    content = (_snapshot(1, "blog", body), *_CONTENT[1:])

    result, _ = _generate(tmp_path, content, settings)

    assert result.success, result.diagnostics
    output = tmp_path / "output"
    hello = (output / "blog/hello/index.html").read_text(encoding="utf-8")
    for fragment in (
        '<link rel="canonical" href="https://geoqiao.github.io/notes/blog/hello/">',
        '<a href="/notes/about/">About</a>',
        '<a href="https://example.com/">elsewhere</a>',
        'src="/notes/assets/images/favicon.png"',
        'href="/notes/assets/css/style.css"',
        '<link rel="icon" href="/notes/assets/images/favicon.png">',
        'content="https://geoqiao.github.io/notes/assets/images/favicon.png"',
        'data-search-index="/notes/search.json"',
    ):
        assert fragment in hello, fragment
    assert all(
        url.startswith("https://geoqiao.github.io/notes/") for url in _sitemap(output)
    )
    assert not (output / "robots.txt").exists()
    assert "url=https://geoqiao.github.io/notes/blog/hello/" in (
        output / "old-hello/index.html"
    ).read_text(encoding="utf-8")


def test_a_theme_address_outside_the_sites_path_names_the_url_filter(
    tmp_path: Path,
) -> None:
    use = _theme(
        tmp_path, {"head-extra.html": '<link rel="stylesheet" href="/assets/x.css">'}
    )
    settings = _settings(site=_UNDER_A_PATH, theme={"use": use})

    result, _ = _generate(tmp_path, _CONTENT, settings)

    assert not result.success
    problems = {d.message for d in result.diagnostics if d.code == "LINK_OUTSIDE_SITE"}
    assert (
        "index.html: link points to /assets/x.css, outside this site at /notes/; "
        "a Theme writes it as {{ '/assets/x.css'|url }}"
    ) in problems
