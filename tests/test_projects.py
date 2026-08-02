from __future__ import annotations

import pytest
from pydantic import ValidationError

from github_blog.config import (
    AboutConfig,
    GithubConfig,
    ProjectCatalogEntry,
    ProjectFallbackMetadata,
    SecurityConfig,
    Settings,
    SiteConfig,
)
from github_blog.projects import ProjectCompiler, ProjectEnrichment
from github_blog.services.render_service import RenderService


def _entry(
    slug: str,
    *,
    order: int = 0,
    featured: bool = False,
    fallback: ProjectFallbackMetadata | None = None,
) -> ProjectCatalogEntry:
    return ProjectCatalogEntry(
        slug=slug,
        title=slug.title(),
        repository=f"geoqiao/{slug}",
        summary=f"About {slug}",
        order=order,
        featured=featured,
        fallback_metadata=fallback,
    )


def test_project_catalog_strict_validation() -> None:
    with pytest.raises(ValidationError):
        ProjectCatalogEntry.model_validate(
            {
                "slug": "x",
                "title": "X",
                "repository": "o/r",
                "summary": "S",
                "extra": True,
            }
        )
    with pytest.raises(ValidationError):
        ProjectFallbackMetadata(stars=-1)
    with pytest.raises(ValidationError):
        ProjectFallbackMetadata(topics=["ok", 2])


def test_projects_sort_feature_and_use_github_links() -> None:
    page = ProjectCompiler().compile(
        [
            _entry("z", order=1),
            _entry("a", order=1, featured=True),
            _entry("first", order=0),
        ]
    )
    assert [project.slug for project in page.projects] == ["first", "a", "z"]
    assert [project.slug for project in page.featured] == ["a"]
    assert page.projects[0].url == "https://github.com/geoqiao/first"
    assert page.canonical_path == "/projects/"


def test_enrichment_failure_falls_back_without_failing() -> None:
    fallback = ProjectFallbackMetadata(
        stars=7, forks=2, language="Python", topics=["tools"]
    )

    def enrich(repository: str) -> ProjectEnrichment:
        if repository.endswith("live"):
            return ProjectEnrichment(
                stars=10, forks=3, language="Rust", topics=("cli",)
            )
        raise RuntimeError("API unavailable")

    page = ProjectCompiler(enrich).compile(
        [_entry("fallback", fallback=fallback), _entry("live")]
    )
    values = {project.slug: project for project in page.projects}
    assert values["fallback"].stars == 7 and values["fallback"].topics == ("tools",)
    assert values["live"].stars == 10 and values["live"].language == "Rust"


def test_empty_projects_page_renders_for_both_themes() -> None:
    page = ProjectCompiler().compile([])
    assert page.projects == ()
    for theme in ("Escape1", "Escape2"):
        settings = Settings(
            github=GithubConfig(repo="geoqiao/site", allowed_authors=["geoqiao"]),
            site=SiteConfig(title="Site", author="G", url="https://geoqiao.me/"),
            about=AboutConfig(issue_number=1),
            security=SecurityConfig(token_env="TOKEN"),  # noqa: S106
            paths={"theme": theme},
        )
        html = RenderService(settings).render_projects(page)
        assert "No projects yet" in html
