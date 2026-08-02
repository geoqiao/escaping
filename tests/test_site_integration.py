from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from github_blog.artifact_validation import SiteArtifactValidator
from github_blog.config import Settings
from github_blog.content_compiler import ContentCompiler
from github_blog.models.issue_snapshot import IssueSnapshot
from github_blog.projects import ProjectCompiler
from github_blog.services.render_service import RenderService
from github_blog.site_model import SiteModelBuilder


def _settings() -> Settings:
    return Settings.model_validate(
        {
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
            "paths": {"theme": "geoqiao.me"},
            "theme_lock": {
                "repository": "geoqiao/escaping",
                "commit": "1003bd7a3a490a17b834ad5f056e56c281fd32ea",
                "api_version": "1",
            },
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
    )


def _snapshot(
    number: int, kind: str, metadata: str, *, labels: tuple[str, ...] = ()
) -> IssueSnapshot:
    created = datetime(2026, 1, number, 12, tzinfo=timezone.utc)
    return IssueSnapshot(
        number=number,
        title={"blog": "A Blog", "idea": "An Idea", "about": "About"}[kind],
        author="geoqiao",
        body=f"---\n{metadata}\n---\n\n# Content\n\nA **safe** body.",
        labels=(f"type:{kind}", "published", *labels),
        created_at=created,
        updated_at=created,
        is_pull_request=False,
    )


def test_representative_content_compiles_to_valid_complete_artifact(
    tmp_path: Path,
) -> None:
    settings = _settings()
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
    content = ContentCompiler(settings).compile(snapshots)
    site = SiteModelBuilder(settings).build(
        content,
        ProjectCompiler().compile(settings.projects),
        build_start_time=datetime(2026, 1, 20, tzinfo=timezone.utc),
    )
    assert not site.has_errors

    renderer = RenderService(settings)
    renderer.copy_theme_assets(tmp_path)
    for output_path, html in renderer.render_site(site).items():
        path = tmp_path / output_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")

    diagnostics = SiteArtifactValidator(settings, site).validate(tmp_path)
    assert diagnostics == []
    assert (tmp_path / "blog" / "a-blog" / "index.html").exists()
    assert (tmp_path / "ideas" / "2" / "index.html").exists()
    assert (tmp_path / "about" / "index.html").exists()
    assert (tmp_path / "projects" / "index.html").exists()
    assert not (tmp_path / "blog" / "a-blog.html").exists()
