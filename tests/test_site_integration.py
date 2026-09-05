from __future__ import annotations

import json
import re
import shutil
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jinja2 import ChoiceLoader, DictLoader, UndefinedError

from escaping.artifact_validation import SiteArtifactValidator
from escaping.config import LocalThemeConfig, Settings
from escaping.content_compiler import ContentCompiler
from escaping.models.issue_snapshot import IssueSnapshot
from escaping.models.site import SiteModel
from escaping.projects import ProjectCompiler
from escaping.routes import RouteRegistry
from escaping.services.render_service import RenderService
from escaping.site_builder import SiteBuilder
from escaping.theme import ThemeLoader

_ROOT = Path(__file__).parent.parent.absolute()


def _settings(theme: str = "geoqiao.me", *, profile_avatar: str = "") -> Settings:
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
        "theme": {"source": "builtin", "name": theme},
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
        assert '<a href="/"' in rendered
        assert '<a href="https://geoqiao.me/"' not in rendered


@pytest.mark.parametrize("theme", ["geoqiao.me", "Escape1", "Escape2", "Quiet"])
def test_front_matter_source_is_separate_from_rendered_body(
    theme: str, tmp_path: Path
) -> None:
    body = "Body sentinel.\n\n```yaml\n---\nslug: literal\n---\n```"
    site = _render_representative_site(_settings(theme), tmp_path, body=body)
    expected = (
        '<p>Body sentinel.</p>\n<pre><code class="language-yaml">'
        "---\nslug: literal\n---\n</code></pre>\n"
    )
    assert site.about is not None
    for page in (*site.blogs, *site.ideas, site.about):
        assert page.body_html == expected
        rendered = (tmp_path / page.route.output_path).read_text(encoding="utf-8")
        assert expected in rendered
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
@pytest.mark.parametrize(
    "article_type",
    [
        "BlogPosting",
        ["Article", "BlogPosting"],
        "https://schema.org/BlogPosting",
        "http://schema.org/TechArticle",
    ],
)
def test_json_ld_page_url_is_distinct_from_referenced_entity_urls(
    graph: bool, article_type: str | list[str], tmp_path: Path
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
    }
    article = {
        "@type": article_type,
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


def test_json_ld_graph_root_and_prefixed_page_identity_are_checked(
    tmp_path: Path,
) -> None:
    site = _render_representative_site(_settings(), tmp_path)
    path = tmp_path / site.blogs[0].route.output_path
    canonical = site.blogs[0].route.canonical_url
    article = {"@type": "s:BlogPosting", "url": canonical}
    document: dict[str, object] = {
        "@context": {"s": "https://schema.org/"},
        "url": canonical,
        "@graph": [article, {"@type": "s:Person", "url": "https://geoqiao.me/about/"}],
    }
    _replace_json_ld(path, document)
    assert SiteArtifactValidator(site).validate(tmp_path) == []
    for target in (document, article):
        target["url"] = "https://wrong.example/"
        _replace_json_ld(path, document)
        assert any(
            d.code == "JSON_LD_URL_MISMATCH"
            for d in SiteArtifactValidator(site).validate(tmp_path)
        )
        target["url"] = canonical
    # An inline primary's author reference must not promote the author to primary.
    document["mainEntity"] = {
        "@type": "BlogPosting",
        "url": canonical,
        "author": {"@id": "#author"},
    }
    document["@graph"] = [
        {
            "@id": "#author",
            "@context": {"s": {"@id": "https://schema.org/", "@prefix": True}},
            "@type": "s:Person",
            "url": "https://geoqiao.me/about/",
        }
    ]
    _replace_json_ld(path, document)
    assert SiteArtifactValidator(site).validate(tmp_path) == []
    # Both a top-level array and a single-node @graph are legal JSON-LD shapes.
    wrong = {"@type": "https://schema.org/Article", "url": "https://wrong.example/"}
    for value in ([wrong], {"@graph": wrong}):
        _replace_json_ld(path, value)
        assert any(
            d.code == "JSON_LD_URL_MISMATCH"
            for d in SiteArtifactValidator(site).validate(tmp_path)
        )


@pytest.mark.parametrize(
    "reference_kind", ["self", "mainEntity", "mainEntityOfPage", "inline"]
)
def test_json_ld_references_cannot_hide_explicit_or_only_page_identity(
    reference_kind: str, tmp_path: Path
) -> None:
    site = _render_representative_site(_settings(), tmp_path)
    article: dict[str, object] = {
        "@id": "#post",
        "@type": "NewsArticle",
        "url": "https://wrong.example/",
    }
    page: dict[str, object] = {
        "@type": "WebPage",
        "url": site.blogs[0].route.canonical_url,
    }
    if reference_kind == "self":
        article["citation"] = {"@id": "#post"}
        document = {"@graph": [article]}
    else:
        page["citation"] = {"@id": "#post"}
        if reference_kind == "mainEntity":
            page["mainEntity"] = {"@id": "#post"}
        elif reference_kind == "inline":
            page["mainEntity"] = article
        else:
            article["mainEntityOfPage"] = {"@id": "#page"}
        document = {"@graph": [article, page]}
    _replace_json_ld(tmp_path / site.blogs[0].route.output_path, document)
    assert any(
        d.code == "JSON_LD_URL_MISMATCH"
        for d in SiteArtifactValidator(site).validate(tmp_path)
    )


def test_local_theme_json_ld_extension_uses_tojson_without_script_breakout(
    tmp_path: Path,
) -> None:
    settings = _settings()
    site = _render_representative_site(settings, tmp_path / "builtin")
    theme_path = tmp_path / "theme"
    shutil.copytree(_ROOT / "src/escaping/themes/geoqiao.me", theme_path)
    template = theme_path / "base.html"
    original = template.read_text(encoding="utf-8")
    template.write_text(
        original.replace(
            "{{ structured_data | tojson }}",
            "{% if post is defined %}{% set _ = structured_data.update(author={'@type': 'Person', 'name': post.title, 'url': 'https://geoqiao.me/about/'}) %}{% endif %}{{ structured_data | tojson }}",
        ),
        encoding="utf-8",
    )
    assert template.read_text(encoding="utf-8") != original
    malicious = '</script><script>alert("title")</script>&'
    site = replace(site, blogs=(replace(site.blogs[0], title=malicious),))
    theme = ThemeLoader(tmp_path).load(
        LocalThemeConfig(name="geoqiao.me", path=Path("theme"))
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
    home = {
        "@graph": [
            {"@type": "Person", "url": "https://geoqiao.me/about/"},
            {"@type": "WebSite", "url": "https://geoqiao.me/"},
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
        '<a href="https://geoqiao.me/Blog/">wrong case</a>',
        '<img src="/Blog/">',
        '<link href="/templates/geoqiao.me/static/css/Style.css" rel="stylesheet">',
        '<img src="/templates/geoqiao.me/static/images/Favicon.png">',
    ],
)
def test_wrong_case_internal_links_and_resources_fail(
    reference: str, tmp_path: Path
) -> None:
    site = _render_representative_site(_settings(), tmp_path)
    path = tmp_path / site.blogs[0].route.output_path
    path.write_text(path.read_text().replace("</body>", reference + "</body>"))
    assert any(
        d.code in {"BROKEN_INTERNAL_LINK", "MISSING_ASSET"}
        for d in SiteArtifactValidator(site).validate(tmp_path)
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


def test_about_description_mismatch_fails_artifact_validation(
    tmp_path: Path,
) -> None:
    settings = _settings()
    site = _render_representative_site(settings, tmp_path)
    about_path = tmp_path / "about" / "index.html"
    about_html = about_path.read_text(encoding="utf-8")
    broken_html = about_html.replace(
        '<meta property="og:description" content="About description.">',
        '<meta property="og:description" content="Wrong description.">',
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
        tmp_path / "templates" / settings.theme.name / "static" / "js" / "prism.js"
    )
    script_path.unlink()

    diagnostics = SiteArtifactValidator(site).validate(tmp_path)
    assert any(
        diagnostic.code == "MISSING_ASSET" and "prism.js" in diagnostic.message
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
    theme = "geoqiao.me"
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
