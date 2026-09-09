from __future__ import annotations

import json
import re
import shutil
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import UTC, datetime
from functools import partial
from html import unescape
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest
from jinja2 import ChoiceLoader, DictLoader, UndefinedError

from escaping.artifact_validation import SiteArtifactValidator
from escaping.config import LocalThemeConfig, Settings
from escaping.content_compiler import ContentCompiler
from escaping.models.content import AboutPage
from escaping.models.issue_snapshot import IssueSnapshot
from escaping.models.site import SiteModel
from escaping.projects import ProjectCompiler
from escaping.routes import RouteRegistry
from escaping.services.render_service import RenderService
from escaping.site_builder import SiteBuilder
from escaping.site_compiler import SiteCompiler
from escaping.theme import ThemeLoader

_ROOT = Path(__file__).parent.parent.absolute()


@pytest.mark.parametrize("theme", ["Quiet", "independent"])
def test_search_artifact_indexes_only_public_content_with_canonical_destinations(
    tmp_path: Path, theme: str
) -> None:
    settings = _settings(theme)
    public = replace(
        _snapshot(1, "blog", "", labels=("tag:python",)),
        title="中文 Python <img src=x onerror=alert(1)>",
        body='A `<button>` & "quoted" summary.',
    )
    snapshots = [
        public,
        replace(public, number=3, labels=("type:blog",), title="PRIVATE DRAFT"),
        replace(public, number=4, author="stranger", title="UNTRUSTED AUTHOR"),
        _snapshot(2, "idea", "", labels=("tag:tools",)),
        _snapshot(10, "about", ""),
    ]
    routes = RouteRegistry(str(settings.site.url))
    content = ContentCompiler(settings, route_registry=routes).compile(snapshots)
    site = SiteBuilder(settings, routes).build(
        content,
        ProjectCompiler().compile(settings.projects, route=routes.projects()),
        build_start_time=datetime(2026, 1, 20, tzinfo=UTC),
    )
    assert not site.has_errors
    renderer = RenderService(ThemeLoader(_ROOT).load(settings.theme))
    renderer.copy_theme_assets(tmp_path)
    artifacts = renderer.render_site(site)
    for name, text in artifacts.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    index = json.loads((tmp_path / "search.json").read_text())
    assert index["version"] == 1
    assert index["items"] == [
        {
            "title": public.title,
            "description": site.blogs[0].description,
            "tags": ["python"],
            "type": "Blog",
            "url": site.blogs[0].route.canonical_path,
        },
        {
            "title": "An Idea",
            "description": site.ideas[0].description,
            "tags": ["tools"],
            "type": "Idea",
            "url": site.ideas[0].route.canonical_path,
        },
        {
            "title": "Escaping",
            "description": "A strict static site compiler.",
            "tags": [],
            "type": "Project",
            "url": "https://github.com/geoqiao/escaping",
        },
    ]
    assert "search.json" not in artifacts["sitemap.xml"]
    assert not SiteArtifactValidator(site).validate(tmp_path)
    # An injected draft / modified destination cannot pass staged publication.
    index["items"][0]["url"] = "javascript:alert(1)"
    (tmp_path / "search.json").write_text(json.dumps(index))
    assert "SEARCH_INDEX_MISMATCH" in {
        d.code for d in SiteArtifactValidator(site).validate(tmp_path)
    }
    (tmp_path / "search.json").write_text("not json")
    assert "INVALID_SEARCH_INDEX" in {
        d.code for d in SiteArtifactValidator(site).validate(tmp_path)
    }


def _settings(theme: str = "Quiet", *, profile_avatar: str = "") -> Settings:
    data: dict[str, object] = {
        "github": {"repo": "geoqiao/site", "allowed_authors": ["geoqiao"]},
        "site": {
            "title": "geoqiao.me",
            "author": "geoqiao",
            "url": "https://geoqiao.me/",
            "description": "A strict personal site.",
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
        "comments": {"enabled": True},
        "theme": {
            "source": "local",
            "name": theme,
            "path": "tests/fixtures/independent_theme",
        }
        if theme == "independent"
        else {"source": "builtin", "name": theme},
        "projects": [
            {
                "slug": "escaping",
                "title": "Escaping",
                "repository": "geoqiao/escaping",
                "summary": "A strict static site compiler.",
                "featured": True,
            }
        ],
    }
    if profile_avatar:
        data["profile"] = {"avatar": profile_avatar}
    return Settings.model_validate(data)


def _snapshot(
    number: int, kind: str, metadata: str, *, labels: tuple[str, ...] = ()
) -> IssueSnapshot:
    created = datetime(2026, 1, number, 12, tzinfo=UTC)
    return IssueSnapshot(
        number=number,
        title={"blog": "A Blog", "idea": "An Idea", "about": "About"}[kind],
        author="geoqiao",
        body=(
            f"---\n{metadata}\n---\n\n# Content\n\nA **safe** body."
            + ("\n\n```yaml\n---\nslug: example\n---\n```" if kind == "blog" else "")
        ),
        labels=(f"type:{kind}", "published", *labels),
        created_at=created,
        updated_at=created,
        is_pull_request=False,
    )


def _render_representative_site(
    settings: Settings, tmp_path: Path, *, body: str | None = None
) -> SiteModel:
    snapshots = [
        _snapshot(
            1,
            "blog",
            'slug: a-blog\ndescription: A blog description.\ncreated_date: "2026-01-01"',
            labels=("tag:python",),
        ),
        _snapshot(
            2,
            "idea",
            'description: An idea description.\ncreated_date: "2026-01-02"',
            labels=("tag:tools",),
        ),
        _snapshot(
            10,
            "about",
            'description: About description.\ncreated_date: "2026-01-03"',
        ),
    ]
    if body is not None:
        snapshots = [
            replace(
                snapshot, body=snapshot.body.split("\n---\n", 1)[0] + "\n---\n\n" + body
            )
            for snapshot in snapshots
        ]
    routes = RouteRegistry(str(settings.site.url))
    content = ContentCompiler(settings, route_registry=routes).compile(snapshots)
    site = SiteBuilder(settings, route_registry=routes).build(
        content,
        ProjectCompiler().compile(settings.projects, route=routes.projects()),
        build_start_time=datetime(2026, 1, 20, tzinfo=UTC),
    )
    assert not site.has_errors
    assert site.home.route is site.routes.route("home")
    assert site.blogs[0].route is site.routes.route("blog-detail-a-blog")
    assert site.archives[0].route is site.routes.route("blog")
    assert site.ideas[0].route is site.routes.route("idea-2")
    assert site.about is not None
    assert site.about.route is site.routes.route("about")
    assert site.projects.route is site.routes.route("projects")
    assert site.tags.route is site.routes.route("tags")
    assert site.tag_archives[0].route is site.routes.route("tag-python")
    assert site.feed.route is site.routes.route("atom")
    assert site.metadata.title == settings.site.title
    assert site.metadata.comments.repo == settings.github.repo
    assert site.metadata.theme.name == settings.theme.name

    renderer = RenderService(ThemeLoader(_ROOT).load(settings.theme))
    renderer.copy_theme_assets(tmp_path)
    for output_path, html in renderer.render_site(site).items():
        path = tmp_path / output_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
    return site


@pytest.mark.parametrize(
    "about_body", ["About body.", "![Picture](https://example.org/p.png)"]
)
def test_defaults_reach_complete_artifacts_with_safe_summaries_and_native_times(
    tmp_path: Path, about_body: str
) -> None:
    created = datetime.fromisoformat("2026-01-02T00:30:00+02:00")
    updated = datetime(2026, 2, 1, tzinfo=UTC)
    summary = 'Use <button> & "</script><script>x".'
    snapshots = [
        replace(
            _snapshot(1, "blog", ""),
            body='Use `<button>` & "`</script><script>x`".',
            created_at=created,
            updated_at=updated,
        ),
        replace(
            _snapshot(3, "blog", ""),
            body='---\ncreated_date: "2000-02-29"\n---\n\nNewer post.',
        ),
        replace(_snapshot(2, "idea", "", labels=("tag:idea-only",)), body="Idea body."),
        replace(_snapshot(10, "about", ""), body=about_body),
    ]

    class Source:
        def get_repo(self, name: str) -> object:
            return object()

        def fetch_issue_snapshots(self, repo: object) -> list[IssueSnapshot]:
            return snapshots

    settings = _settings().model_copy(update={"projects": []})
    result = SiteCompiler(
        "unused",
        settings.github.repo,
        settings,
        config_root=tmp_path,
        github_service=Source(),
    ).generate()
    assert result.success, result.diagnostics
    output = tmp_path / settings.paths.output
    blog = (output / "blog/1/index.html").read_text()
    for key in (
        'name="description"',
        'property="og:description"',
        'name="twitter:description"',
    ):
        meta = re.search(rf'<meta {key} content="([^"]*)">', blog)
        assert meta is not None and unescape(meta[1]) == summary
    assert '<time datetime="2026-01-01">' in blog
    assert 'data-issue-number="1"' in blog
    script = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', blog, re.DOTALL
    )
    assert script is not None and json.loads(script[1])["description"] == summary
    assert "</script><script>x" not in blog
    feed = ET.fromstring((output / "atom.xml").read_bytes())  # noqa: S314 - locally generated XML
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entries = feed.findall("a:entry", ns)
    assert [entry.findtext("a:id", namespaces=ns) for entry in entries] == [
        "https://geoqiao.me/blog/3/",
        "https://geoqiao.me/blog/1/",
    ]
    assert entries[1].findtext("a:summary", namespaces=ns) == summary
    assert entries[1].findtext("a:published", namespaces=ns) == "2026-01-01T22:30:00Z"
    assert entries[1].findtext("a:updated", namespaces=ns) == "2026-02-01T00:00:00Z"
    assert feed.findtext("a:updated", namespaces=ns) == "2026-02-01T00:00:00Z"
    archive = (output / "blog/index.html").read_text()
    assert archive.index('href="/blog/3/"') < archive.index('href="/blog/1/"')
    assert '<time datetime="2000-02-29">' in (output / "blog/3/index.html").read_text()
    assert (output / "ideas/2/index.html").exists()
    assert not (output / "tags/idea-only").exists()
    about = (output / "about/index.html").read_text()
    expected_about = "About body." if about_body == "About body." else ""
    assert f'<meta name="description" content="{expected_about}">' in about


def test_representative_content_compiles_to_valid_complete_artifact(
    tmp_path: Path,
) -> None:
    settings = _settings()
    site = _render_representative_site(settings, tmp_path)
    diagnostics = SiteArtifactValidator(site).validate(tmp_path)
    assert diagnostics == []
    assert (tmp_path / "blog" / "a-blog" / "index.html").exists()
    assert (tmp_path / "ideas" / "2" / "index.html").exists()
    assert (tmp_path / "about" / "index.html").exists()
    assert (tmp_path / "projects" / "index.html").exists()
    assert not (tmp_path / "blog" / "a-blog.html").exists()
    for output_path in ("index.html", "blog/index.html"):
        rendered = (tmp_path / output_path).read_text(encoding="utf-8")
        assert re.search(r'<a\b[^>]*\bhref="/"', rendered)
        assert not re.search(r'<a\b[^>]*\bhref="https://geoqiao.me/"', rendered)


@pytest.mark.parametrize("theme", ["Quiet", "independent"])
def test_front_matter_source_is_separate_from_rendered_body(
    theme: str, tmp_path: Path
) -> None:
    body = "Body sentinel.\n\n```yaml\n---\nslug: literal\n---\n```"
    site = _render_representative_site(_settings(theme), tmp_path, body=body)
    assert isinstance(site.about, AboutPage)
    for page in (*site.blogs, *site.ideas, site.about):
        body_tree = ET.fromstring(f"<div>{page.body_html}</div>")  # noqa: S314
        assert body_tree.findtext("p") == "Body sentinel."
        code = body_tree.find("pre/code")
        assert code is not None
        assert "".join(code.itertext()) == "---\nslug: literal\n---\n"
        rendered = (tmp_path / page.route.output_path).read_text(encoding="utf-8")
        assert page.body_html in rendered
        assert "created_date:" not in rendered
        assert "description:" not in rendered
    assert SiteArtifactValidator(site).validate(tmp_path) == []

    # A Theme cannot accidentally select the original Issue envelope: its only
    # body input is compiled body_html, not an IssueSnapshot or raw Markdown.
    renderer = RenderService(ThemeLoader(_ROOT).load(_settings(theme).theme))
    assert renderer.env.loader is not None
    renderer.env.loader = ChoiceLoader(
        [DictLoader({"post.html": "{{ post.body | safe }}"}), renderer.env.loader]
    )
    with pytest.raises(UndefinedError, match="body"):
        renderer.render_site(site)


@pytest.mark.parametrize(
    "body",
    [
        "slug: is the URL identifier, explained here.",
        "created_date: is the original writing date.",
        "Before.\n\n---\n\nAfter.",
        "<p>---</p>",
    ],
)
def test_authored_metadata_terms_and_separators_are_not_leaks(
    body: str, tmp_path: Path
) -> None:
    site = _render_representative_site(_settings(), tmp_path, body=body)
    assert SiteArtifactValidator(site).validate(tmp_path) == []


def _replace_json_ld(path: Path, value: object) -> None:
    html = path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'(<script type="application/ld\+json">).*?(</script>)',
        lambda match: match[1] + json.dumps(value) + match[2],
        html,
        count=1,
        flags=re.DOTALL,
    )
    assert count == 1
    path.write_text(updated, encoding="utf-8")


@pytest.mark.parametrize("graph", [False, True])
def test_json_ld_page_url_is_distinct_from_referenced_entity_urls(
    graph: bool, tmp_path: Path
) -> None:
    site = _render_representative_site(_settings(), tmp_path)
    post = site.blogs[0]
    path = tmp_path / post.route.output_path
    author = {"@type": "Person", "@id": "#author", "url": "https://geoqiao.me/about/"}
    website = {"@type": "WebSite", "url": "https://geoqiao.me/"}
    related = {
        "@type": "BlogPosting",
        "@id": "#related",
        "url": "https://other.example/post/",
        "mainEntityOfPage": "https://other.example/post/",
    }
    article = {
        "@id": post.route.canonical_url,
        "@type": "BlogPosting",
        "url": post.route.canonical_url,
        "author": author,
        "isPartOf": website,
        "citation": {"@id": "#related"} if graph else related,
    }
    document = {"@graph": [author, website, article, related]} if graph else article
    _replace_json_ld(path, document)
    assert SiteArtifactValidator(site).validate(tmp_path) == []
    article["url"] = "https://geoqiao.me/blog/wrong/"
    _replace_json_ld(path, document)
    assert any(
        d.code == "JSON_LD_URL_MISMATCH"
        for d in SiteArtifactValidator(site).validate(tmp_path)
    )


def test_json_ld_checks_provided_root_and_explicit_page_urls(tmp_path: Path) -> None:
    site = _render_representative_site(_settings(), tmp_path)
    path = tmp_path / site.blogs[0].route.output_path
    canonical = site.blogs[0].route.canonical_url
    page: dict[str, object] = {"@id": canonical}
    document: dict[str, object] = {"@graph": [page]}
    # URL is optional, but any supplied URL must be a canonical string.
    _replace_json_ld(path, document)
    assert SiteArtifactValidator(site).validate(tmp_path) == []
    for target in (document, page):
        for url in ("https://wrong.example/", None, {"@id": canonical}, [canonical]):
            target["url"] = url
            _replace_json_ld(path, document)
            assert any(
                d.code == "JSON_LD_URL_MISMATCH"
                for d in SiteArtifactValidator(site).validate(tmp_path)
            ), (target, url)
        target["url"] = canonical


@pytest.mark.parametrize("identity", ["missing", "wrong", "author", "duplicate"])
def test_json_ld_graph_requires_one_exact_page_id(
    identity: str, tmp_path: Path
) -> None:
    site = _render_representative_site(_settings(), tmp_path)
    canonical = site.blogs[0].route.canonical_url
    page = {"@id": canonical, "url": canonical}
    nodes = [page]
    if identity == "missing":
        del page["@id"]
    elif identity == "wrong":
        page.update({"@id": "https://wrong.example/", "url": "https://wrong.example/"})
    elif identity == "author":
        page["@id"] += "#author"
    else:
        nodes.append(dict(page))
    _replace_json_ld(tmp_path / site.blogs[0].route.output_path, {"@graph": nodes})
    assert any(
        d.code == "JSON_LD_PAGE_IDENTITY"
        for d in SiteArtifactValidator(site).validate(tmp_path)
    )


@pytest.mark.parametrize("value", [[], {"@graph": {}}, {"@graph": [None]}])
def test_json_ld_unsupported_shapes_fail_explicitly(
    value: object, tmp_path: Path
) -> None:
    site = _render_representative_site(_settings(), tmp_path)
    _replace_json_ld(tmp_path / site.blogs[0].route.output_path, value)
    assert any(
        d.code == "INVALID_JSON_LD"
        for d in SiteArtifactValidator(site).validate(tmp_path)
    )


def test_local_theme_json_ld_extension_uses_tojson_without_script_breakout(
    tmp_path: Path,
) -> None:
    settings = _settings()
    site = _render_representative_site(settings, tmp_path / "builtin")
    theme_path = tmp_path / "theme"
    shutil.copytree(_ROOT / "src/escaping/themes/Quiet", theme_path)
    template = theme_path / "base.html"
    original = template.read_text(encoding="utf-8")
    template.write_text(
        original.replace(
            "{{ structured_data|tojson }}",
            "{% if post is defined %}{% set _ = structured_data.update(author={'@type': 'Person', 'name': post.title, 'url': 'https://geoqiao.me/about/'}) %}{% endif %}{{ structured_data|tojson }}",
        ),
        encoding="utf-8",
    )
    assert template.read_text(encoding="utf-8") != original
    malicious = '</script><script>alert("title")</script>&'
    site = replace(site, blogs=(replace(site.blogs[0], title=malicious),))
    theme = ThemeLoader(tmp_path).load(
        LocalThemeConfig(name="Quiet", path=Path("theme"))
    )
    renderer = RenderService(theme)
    output = tmp_path / "local-output"
    renderer.copy_theme_assets(output)
    for output_path, html in renderer.render_site(site).items():
        path = output / output_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
    assert SiteArtifactValidator(site).validate(output) == []
    html = (output / site.blogs[0].route.output_path).read_text(encoding="utf-8")
    assert malicious not in html
    script = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL
    )
    assert script is not None
    assert "\\u003c/script\\u003e" in script[1]
    assert json.loads(script[1])["author"]["name"] == malicious
    assert json.loads(script[1])["url"] == site.blogs[0].route.canonical_url


def test_json_ld_home_and_about_identity_and_json_parsing_remain_checked(
    tmp_path: Path,
) -> None:
    site = _render_representative_site(_settings(), tmp_path)
    home_path = tmp_path / "index.html"
    script = re.search(
        r'<script type="application/ld\+json">(.*?)</script>',
        home_path.read_text(),
        re.DOTALL,
    )
    assert script is not None
    assert (
        sum(
            node.get("@id") == site.home.route.canonical_url
            for node in json.loads(script[1])["@graph"]
        )
        == 1
    )
    home = {
        "@graph": [
            {"@type": "Person", "url": "https://geoqiao.me/about/"},
            {
                "@id": "https://geoqiao.me/",
                "@type": "WebSite",
                "url": "https://geoqiao.me/",
            },
        ]
    }
    _replace_json_ld(home_path, home)
    assert SiteArtifactValidator(site).validate(tmp_path) == []
    home["@graph"][1]["url"] = "https://wrong.example/"
    _replace_json_ld(home_path, home)
    _replace_json_ld(
        tmp_path / "about/index.html",
        {"@type": "Person", "url": "https://wrong.example/"},
    )
    post_path = tmp_path / site.blogs[0].route.output_path
    post_path.write_text(
        post_path.read_text().replace(
            'application/ld+json">', 'application/ld+json">INVALID', 1
        )
    )
    codes = [d.code for d in SiteArtifactValidator(site).validate(tmp_path)]
    assert codes.count("JSON_LD_URL_MISMATCH") == 2
    assert "INVALID_JSON_LD" in codes


@pytest.mark.parametrize(
    "reference",
    [
        '<a href="/Blog/">wrong case</a>',
        '<a href="/%62log/">encoded page alias</a>',
        '<a href="https://geoqiao.me/Blog/">wrong case</a>',
        '<img src="/Blog/">',
        '<link href="/templates/Quiet/static/css/Style.css" rel="stylesheet">',
        '<img src="/templates/Quiet/static/images/Favicon.png">',
    ],
)
def test_noncanonical_internal_links_and_resources_fail(
    reference: str, tmp_path: Path
) -> None:
    site = _render_representative_site(_settings(), tmp_path)
    path = tmp_path / site.blogs[0].route.output_path
    path.write_text(path.read_text().replace("</body>", reference + "</body>"))
    assert any(
        d.code in {"BROKEN_INTERNAL_LINK", "MISSING_ASSET"}
        for d in SiteArtifactValidator(site).validate(tmp_path)
    )


@pytest.mark.parametrize(
    "filename,url_name,status,valid",
    [
        ("encoded%20name.txt", "encoded%20name.txt", 404, False),
        ("encoded%20name.txt", "encoded%2520name.txt?download=1#file", 200, True),
        ("space name.txt", "space%20name.txt", 200, True),
        ("雪.txt", "%E9%9B%AA.txt", 200, True),
    ],
)
def test_static_file_urls_decode_once_like_local_http(
    filename: str, url_name: str, status: int, valid: bool, tmp_path: Path
) -> None:
    site = _render_representative_site(_settings(), tmp_path)
    prefix = f"{site.metadata.theme.asset_path}/static/"
    asset = tmp_path / prefix.lstrip("/") / filename
    asset.write_text("Asset sentinel.", encoding="utf-8")
    path = tmp_path / site.blogs[0].route.output_path
    original = path.read_text()
    url = prefix + url_name
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
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
        assert actual_status == status
        for tag, attr in (("a", "href"), ("img", "src")):
            reference = f'<{tag} {attr}="{url}"></{tag}>'
            path.write_text(original.replace("</body>", reference + "</body>"))
            diagnostics = SiteArtifactValidator(site).validate(tmp_path)
            if valid:
                assert diagnostics == []
            else:
                assert any(d.code == "MISSING_ASSET" for d in diagnostics)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize(
    "filename,url_name",
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
def test_unsafe_static_url_paths_fail_before_normalization(
    filename: str, url_name: str, tmp_path: Path
) -> None:
    site = _render_representative_site(_settings(), tmp_path)
    prefix = f"{site.metadata.theme.asset_path}/static/"
    asset = tmp_path / prefix.lstrip("/") / filename
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_text("Must not authorize an unsafe URL.", encoding="utf-8")
    path = tmp_path / site.blogs[0].route.output_path
    original = path.read_text()
    for tag, attr in (("a", "href"), ("img", "src")):
        reference = f'<{tag} {attr}="{prefix}{url_name}"></{tag}>'
        path.write_text(original.replace("</body>", reference + "</body>"))
        assert any(
            d.code == "INVALID_INTERNAL_PATH"
            for d in SiteArtifactValidator(site).validate(tmp_path)
        )


def test_static_asset_symlink_is_not_a_contained_emitted_file(tmp_path: Path) -> None:
    output = tmp_path / "candidate"
    site = _render_representative_site(_settings(), output)
    outside = tmp_path / "outside.txt"
    outside.write_text("Outside candidate.")
    url = f"{site.metadata.theme.asset_path}/static/escape.txt"
    (output / url.lstrip("/")).symlink_to(outside)
    path = output / site.blogs[0].route.output_path
    original = path.read_text()
    for tag, attr in (("a", "href"), ("img", "src")):
        path.write_text(
            original.replace("</body>", f'<{tag} {attr}="{url}"></{tag}></body>')
        )
        assert any(
            d.code == "MISSING_ASSET"
            for d in SiteArtifactValidator(site).validate(output)
        )


@pytest.mark.parametrize("artifact", ["blog/a-blog/index.html", "atom.xml"])
def test_wrong_case_artifact_filename_is_not_an_existing_route(
    artifact: str, tmp_path: Path
) -> None:
    site = _render_representative_site(_settings(), tmp_path)
    path = tmp_path / artifact
    path.rename(path.with_name(path.name.upper()))
    assert any(
        d.code == "MISSING_ROUTE"
        for d in SiteArtifactValidator(site).validate(tmp_path)
    )


def test_atom_entry_lookup_requires_exact_route_case(tmp_path: Path) -> None:
    site = _render_representative_site(_settings(), tmp_path)
    path = tmp_path / "atom.xml"
    path.write_text(path.read_text().replace("/blog/a-blog/", "/Blog/a-blog/"))
    assert any(
        d.code == "ATOM_ENTRY_ROUTE"
        for d in SiteArtifactValidator(site).validate(tmp_path)
    )


@pytest.mark.parametrize(
    "replacement",
    [
        '<meta property="og:description" content="Wrong description.">',
        '<meta property="og:description">',
        "",
    ],
)
@pytest.mark.parametrize("description", ["About description.", ""])
def test_about_description_mismatch_fails_artifact_validation(
    tmp_path: Path,
    replacement: str,
    description: str,
) -> None:
    settings = _settings()
    site = _render_representative_site(settings, tmp_path)
    assert site.about is not None
    site = replace(site, about=replace(site.about, description=description))
    about_path = tmp_path / "about" / "index.html"
    about_html = about_path.read_text(encoding="utf-8").replace(
        "About description.", description
    )
    about_path.write_text(about_html, encoding="utf-8")
    assert SiteArtifactValidator(site).validate(tmp_path) == []
    broken_html = about_html.replace(
        f'<meta property="og:description" content="{description}">',
        replacement,
        1,
    )
    assert broken_html != about_html
    about_path.write_text(broken_html, encoding="utf-8")

    diagnostics = SiteArtifactValidator(site).validate(tmp_path)
    assert any(
        diagnostic.code == "ABOUT_DESCRIPTION_MISMATCH" for diagnostic in diagnostics
    )


def test_missing_referenced_script_fails_artifact_validation(
    tmp_path: Path,
) -> None:
    settings = _settings()
    site = _render_representative_site(settings, tmp_path)
    script_path = (
        tmp_path / "templates" / settings.theme.name / "static" / "js" / "site.js"
    )
    script_path.unlink()

    diagnostics = SiteArtifactValidator(site).validate(tmp_path)
    assert any(
        diagnostic.code == "MISSING_ASSET" and "site.js" in diagnostic.message
        for diagnostic in diagnostics
    )


def test_missing_deferred_runtime_asset_fails_artifact_validation(
    tmp_path: Path,
) -> None:
    settings = _settings()
    site = _render_representative_site(settings, tmp_path)
    mermaid_path = next(
        (tmp_path / "templates" / settings.theme.name / "static/vendor").glob(
            "mermaid-*/mermaid.min.js"
        )
    )
    mermaid_path.unlink()

    diagnostics = SiteArtifactValidator(site).validate(tmp_path)
    assert any(
        diagnostic.code == "MISSING_ASSET" and "mermaid.min.js" in diagnostic.message
        for diagnostic in diagnostics
    )


def test_missing_same_origin_absolute_asset_fails_artifact_validation(
    tmp_path: Path,
) -> None:
    settings = _settings()
    theme = settings.theme.name
    site = _render_representative_site(settings, tmp_path)
    asset_dir = tmp_path / "templates" / theme / "static" / "css"
    asset_path = asset_dir / "absolute.css"
    asset_path.write_text("", encoding="utf-8")
    about_path = tmp_path / "about" / "index.html"
    about_html = about_path.read_text(encoding="utf-8")
    reference = (
        f'<link rel="stylesheet" href="https://geoqiao.me/templates/{theme}'
        '/static/css/absolute.css?cache=1#style">'
    )
    about_path.write_text(
        about_html.replace("</head>", f"{reference}</head>", 1), encoding="utf-8"
    )
    assert SiteArtifactValidator(site).validate(tmp_path) == []
    asset_path.unlink()

    diagnostics = SiteArtifactValidator(site).validate(tmp_path)
    assert any(
        diagnostic.code == "MISSING_ASSET" and "absolute.css" in diagnostic.message
        for diagnostic in diagnostics
    )


def test_missing_referenced_image_fails_artifact_validation(
    tmp_path: Path,
) -> None:
    theme = "Quiet"
    profile_avatar = (
        f"https://geoqiao.me/templates/{theme}/static/images/profile.png?cache=1#avatar"
    )
    settings = _settings(profile_avatar=profile_avatar)
    site = _render_representative_site(settings, tmp_path)
    image_dir = tmp_path / "templates" / theme / "static" / "images"
    image_bytes = (image_dir / "favicon.png").read_bytes()
    for filename in ("profile.png", "responsive.png", "other.png"):
        (image_dir / filename).write_bytes(image_bytes)

    about_path = tmp_path / "about" / "index.html"
    about_html = about_path.read_text(encoding="utf-8")
    srcset = (
        f"/templates/{theme}/static/images/responsive.png?width=1 1x,"
        f" /templates/{theme}/static/images/other.png#wide 2x"
    )
    about_html = about_html.replace(
        f'src="{profile_avatar}"',
        f'src="{profile_avatar}" srcset="{srcset}"',
        1,
    )
    about_path.write_text(about_html, encoding="utf-8")
    assert SiteArtifactValidator(site).validate(tmp_path) == []

    (image_dir / "profile.png").unlink()
    (image_dir / "responsive.png").unlink()
    diagnostics = SiteArtifactValidator(site).validate(tmp_path)
    assert any(
        diagnostic.code == "MISSING_ASSET" and "profile.png" in diagnostic.message
        for diagnostic in diagnostics
    )
    assert any(
        diagnostic.code == "MISSING_ASSET" and "responsive.png" in diagnostic.message
        for diagnostic in diagnostics
    )
