from __future__ import annotations

import pytest
from pydantic import ValidationError

from github_blog.config import ProjectCatalogEntry, ProjectFallbackMetadata
from github_blog.projects import ProjectCompiler, ProjectEnrichment
from github_blog.routes import Route, RouteRegistry


def _projects_route() -> Route:
    return RouteRegistry("https://geoqiao.me/").projects()


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
        ProjectFallbackMetadata.model_validate({"topics": ["ok", 2]})


def test_projects_sort_feature_and_use_github_links() -> None:
    page = ProjectCompiler().compile(
        [
            _entry("z", order=1),
            _entry("a", order=1, featured=True),
            _entry("first", order=0),
        ],
        route=_projects_route(),
    )
    assert [project.slug for project in page.projects] == ["first", "a", "z"]
    assert [project.slug for project in page.featured] == ["a"]
    assert page.projects[0].url == "https://github.com/geoqiao/first"
    assert page.canonical_path == "/projects/"


def test_projects_rank_top_five_by_stars_with_catalog_order_tiebreaker() -> None:
    def metadata(stars: int | None) -> ProjectFallbackMetadata:
        return ProjectFallbackMetadata(stars=stars)

    page = ProjectCompiler().compile(
        [
            _entry("unknown", order=0),
            _entry("ten-later", order=4, fallback=metadata(10)),
            _entry("one", order=1, fallback=metadata(1)),
            _entry("zero", order=6, fallback=metadata(0)),
            _entry("eight", order=5, fallback=metadata(8)),
            _entry("ten-first", order=2, fallback=metadata(10)),
            _entry("four", order=3, fallback=metadata(4)),
        ],
        route=_projects_route(),
    )

    assert [project.slug for project in page.top_by_stars()] == [
        "ten-first",
        "ten-later",
        "eight",
        "four",
        "one",
    ]


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
        [_entry("fallback", fallback=fallback), _entry("live")],
        route=_projects_route(),
    )
    values = {project.slug: project for project in page.projects}
    assert values["fallback"].stars == 7 and values["fallback"].topics == ("tools",)
    assert values["live"].stars == 10 and values["live"].language == "Rust"
