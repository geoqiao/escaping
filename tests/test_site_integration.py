from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from escaping.artifact_validation import SiteArtifactValidator
from escaping.config import Settings
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
    created = datetime(2026, 1, number, 12, tzinfo=timezone.utc)
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


def _render_representative_site(settings: Settings, tmp_path: Path) -> SiteModel:
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
    routes = RouteRegistry(str(settings.site.url))
    content = ContentCompiler(settings, route_registry=routes).compile(snapshots)
    site = SiteBuilder(settings, route_registry=routes).build(
        content,
        ProjectCompiler().compile(settings.projects, route=routes.projects()),
        build_start_time=datetime(2026, 1, 20, tzinfo=timezone.utc),
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
