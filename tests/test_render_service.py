"""The render context Themes receive: site, page, theme and t."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from escaping.artifact_validation import SiteArtifactValidator
from escaping.config import Settings
from escaping.models.issue_snapshot import IssueSnapshot
from escaping.services.render_service import RenderedSite
from escaping.site_compiler import check_theme, compile_site, prepare_theme, render_site

_ROOT = Path(__file__).parent.parent.absolute()
_NOW = datetime(2026, 1, 20, tzinfo=UTC)


def _settings(
    use: str, *, site: dict[str, object] | None = None, **sections: object
) -> Settings:
    return Settings.model_validate(
        {
            "github": {"repo": "geoqiao/site", "allowed_authors": ["geoqiao"]},
            "site": {
                "title": "Site",
                "author": "geoqiao",
                "url": "https://geoqiao.me/",
                "description": "Notes and tools.",
                **(site or {}),
            },
            "about": {"issue_number": 10},
            "theme": {"use": use},
            **sections,
        }
    )


def _issue(number: int, kind: str, title: str) -> IssueSnapshot:
    created = datetime(2026, 1, number, tzinfo=UTC)
    return IssueSnapshot(
        number,
        title,
        "geoqiao",
        "Body.",
        ("published", f"type:{kind}"),
        created,
        created,
        False,
    )


_ABOUT = _issue(10, "about", "About")


def _render(
    config_root: Path, settings: Settings, content: list[IssueSnapshot]
) -> RenderedSite:
    theme, options = prepare_theme(settings, config_root)
    site = compile_site(
        settings, content, theme, project_enricher=None, build_start_time=_NOW
    )
    assert not site.has_errors, site.diagnostics
    output = config_root / "output"
    rendered = render_site(output, site, theme, options)
    assert SiteArtifactValidator(site).validate(output) == []
    return rendered


def _extends_fixture(root: Path) -> str:
    """A copy, so the build output stays out of the checkout."""
    shutil.copytree(_ROOT / "tests/fixtures/extends_theme", root / "theme")
    return "./theme"


def _home_probe(root: Path, home: str, manifest: str = "") -> str:
    """A Theme that extends Quiet and replaces only home.html."""
    theme = root / "theme"
    theme.mkdir()
    (theme / "theme.yaml").write_text(f"api: 3\nextends: quiet\n{manifest}")
    (theme / "home.html").write_text(home)
    return "./theme"


def test_posts_options_become_blog_posts_in_configured_order(tmp_path: Path) -> None:
    use = _home_probe(
        tmp_path,
        "{% for post in theme.picks %}{{ post.issue_number }}:{{ post.title }};"
        "{% endfor %}|{{ theme.featured_posts|length }}",
        "options:\n  picks: {type: posts, default: []}\n",
    )
    settings = _settings(use, theme={"use": use, "options": {"picks": [3, 99, 1, 2]}})
    content = [
        _issue(1, "blog", "First"),
        _issue(2, "idea", "An idea"),
        _issue(3, "blog", "Third"),
        _ABOUT,
    ]

    rendered = _render(tmp_path, settings, content)

    assert rendered.files["index.html"] == "3:Third;1:First;|0"
    assert [
        (d.severity, d.code, d.issue_number, d.field) for d in rendered.diagnostics
    ] == [
        ("warning", "THEME_OPTION_POST_MISSING", 99, "theme.options.picks"),
        ("warning", "THEME_OPTION_POST_MISSING", 2, "theme.options.picks"),
    ]
    assert rendered.diagnostics[0].message == (
        "theme.options.picks: Issue #99 is not a published Blog post; it is left out"
    )


def test_site_context_lists_projects_and_featured_projects_in_order(
    tmp_path: Path,
) -> None:
    use = _home_probe(
        tmp_path,
        "{% for p in site.projects %}{{ p.slug }} {% endfor %}|"
        "{% for p in site.featured_projects %}{{ p.slug }} {% endfor %}",
    )
    projects = [
        {"repository": "owner/ignored", "order": 0},
        {"repository": "owner/second", "featured": True, "order": 2},
        {"repository": "owner/first", "featured": True, "order": 1},
        {"repository": "owner/last", "featured": True, "order": 3},
    ]

    rendered = _render(tmp_path, _settings(use, projects=projects), [_ABOUT])

    assert (
        rendered.files["index.html"] == "ignored first second last |first second last "
    )


def test_named_site_routes_exist_without_posts_or_ideas(tmp_path: Path) -> None:
    names = ("home", "blog", "ideas", "about", "projects", "tags", "atom", "search")
    use = _home_probe(
        tmp_path,
        "{% for route in ["
        + ", ".join(f"site.routes.{name}" for name in names)
        + "] %}{{ route.canonical_path }}|{{ route.canonical_url }}\n{% endfor %}",
    )

    rendered = _render(tmp_path, _settings(use), [_ABOUT])

    assert rendered.files["index.html"].splitlines() == [
        "/|https://geoqiao.me/",
        "/blog/|https://geoqiao.me/blog/",
        "/ideas/|https://geoqiao.me/ideas/",
        "/about/|https://geoqiao.me/about/",
        "/projects/|https://geoqiao.me/projects/",
        "/tags/|https://geoqiao.me/tags/",
        "/atom.xml|https://geoqiao.me/atom.xml",
        "/search.json|https://geoqiao.me/search.json",
    ]
    for path in ("blog/index.html", "ideas/index.html", "tags/index.html"):
        assert path in rendered.files


def test_a_theme_without_404_html_publishes_none(tmp_path: Path) -> None:
    shutil.copytree(_ROOT / "tests/fixtures/independent_theme", tmp_path / "theme")
    (tmp_path / "theme" / "404.html").unlink()

    rendered = _render(tmp_path, _settings("./theme"), [_ABOUT])

    assert "404.html" not in rendered.files
    assert "index.html" in rendered.files


def test_theme_pages_render_once_and_once_per_project(tmp_path: Path) -> None:
    projects = [
        {
            "repository": "geoqiao/alpha",
            "title": "Alpha",
            "summary": "A small tool.",
            "featured": True,
        },
        {"website": "https://beta.example.com/", "slug": "beta", "title": "Beta"},
    ]
    settings = _settings(_extends_fixture(tmp_path), projects=projects)

    files = _render(tmp_path, settings, [_ABOUT]).files

    now = files["now/index.html"]
    assert "<title>Now · Site</title>" in now
    assert '<link rel="canonical" href="https://geoqiao.me/now/">' in now
    assert '<p class="now-text">Working on escaping.</p>' in now
    alpha = files["projects/alpha/index.html"]
    assert "<title>Alpha · Site</title>" in alpha
    assert '<meta name="description" content="A small tool.">' in alpha
    assert "<h1>Alpha</h1>" in alpha and "<p>A small tool.</p>" in alpha
    assert '<a href="/projects/">All projects</a>' in alpha
    assert (
        '<meta name="description" content="Notes and tools.">'
        in (files["projects/beta/index.html"])
    )
    # Project links and the search index point at the Theme's detail pages.
    assert (
        '<h2><a href="/projects/alpha/">Alpha</a></h2>' in files["projects/index.html"]
    )
    assert '<h2><a href="/projects/beta/">Beta</a></h2>' in files["projects/index.html"]
    assert '<h3><a href="/projects/alpha/">Alpha' in files["index.html"]
    search = json.loads(files["search.json"])["items"]
    assert {
        item["title"]: item["url"] for item in search if item["type"] == "Project"
    } == {
        "Alpha": "/projects/alpha/",
        "Beta": "/projects/beta/",
    }
    for url in ("now/", "projects/alpha/", "projects/beta/"):
        assert f"<loc>https://geoqiao.me/{url}</loc>" in files["sitemap.xml"]


def test_theme_pages_use_strings_from_every_layer(tmp_path: Path) -> None:
    settings = _settings(
        _extends_fixture(tmp_path),
        site={"language": "zh"},
        projects=[{"repository": "geoqiao/alpha", "title": "Alpha"}],
    )

    files = _render(tmp_path, settings, [_ABOUT]).files

    assert "<h1>现在</h1>" in files["now/index.html"]
    assert '<a href="/projects/">全部项目</a>' in files["projects/alpha/index.html"]


def test_theme_check_reports_a_template_that_fails_while_rendering(
    tmp_path: Path,
) -> None:
    use = _home_probe(tmp_path, "<p>\n{{ t.no_such_key }}</p>")

    result = check_theme(_settings(use), config_root=tmp_path)

    assert not result.success
    assert [d.code for d in result.diagnostics] == ["TEMPLATE_RENDER_FAILED"]
    # The author learns which file and line to fix.
    assert result.diagnostics[0].message.startswith("./theme/home.html line 2: ")
    assert "no_such_key" in result.diagnostics[0].message
