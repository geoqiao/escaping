from __future__ import annotations

import pytest
from pydantic import ValidationError

from escaping.config import Link, ProjectCatalogEntry, ProjectFallbackMetadata
from escaping.models.projects import ProjectLink
from escaping.projects import ProjectCompiler, ProjectEnrichment
from escaping.routes import Route, RouteRegistry


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
    result = ProjectCompiler().compile(
        [
            _entry("z", order=1, featured=True),
            _entry("a", order=1, featured=True),
            _entry("first", order=0),
        ],
        route=_projects_route(),
    )
    page = result.page
    assert [project.slug for project in page.projects] == ["first", "a", "z"]
    assert [project.slug for project in page.featured] == ["a", "z"]
    assert page.projects[0].url == "https://github.com/geoqiao/first"
    assert page.canonical_path == "/projects/"


def test_compiler_preserves_project_visual_fields_as_immutable_data() -> None:
    result = ProjectCompiler().compile(
        [
            ProjectCatalogEntry(
                repository="geoqiao/visual",
                image="/templates/my-theme/static/images/visual.webp",
                links=[Link(name="Demo", url="https://example.org/")],
            )
        ],
        route=_projects_route(),
    )
    project = result.page.projects[0]
    assert project.image == "/templates/my-theme/static/images/visual.webp"
    assert isinstance(project.links, tuple)
    assert isinstance(project.links[0], ProjectLink)
    assert (project.links[0].name, project.links[0].url) == (
        "Demo",
        "https://example.org/",
    )


def test_projects_rank_top_five_by_stars_with_catalog_order_tiebreaker() -> None:
    def metadata(stars: int | None) -> ProjectFallbackMetadata:
        return ProjectFallbackMetadata(stars=stars)

    result = ProjectCompiler().compile(
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

    assert [project.slug for project in result.page.top_by_stars()] == [
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

    result = ProjectCompiler(enrich).compile(
        [_entry("fallback", fallback=fallback), _entry("live")],
        route=_projects_route(),
    )
    values = {project.slug: project for project in result.page.projects}
    assert values["fallback"].stars == 7 and values["fallback"].topics == ("tools",)
    assert values["live"].stars == 10 and values["live"].language == "Rust"
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "PROJECT_ENRICHMENT_FAILED"
    ]
    diagnostic = result.diagnostics[0]
    assert diagnostic.severity == "warning"
    assert diagnostic.field == "projects.fallback"
    assert "geoqiao/fallback" in diagnostic.message
    assert "API unavailable" not in diagnostic.message


def test_repository_only_projects_preserve_keys_choices_and_explicit_empty_values() -> (
    None
):
    def enrich(repository: str) -> ProjectEnrichment:
        return ProjectEnrichment(
            name="Renamed", description="Public description", stars=12
        )

    entries = [
        ProjectCatalogEntry(repository="Alice/Tool"),
        ProjectCatalogEntry(repository="Bob/Tool", title="Manual", summary=""),
        ProjectCatalogEntry(repository="Alice/Tool", slug="UNCHANGED"),
    ]
    result = ProjectCompiler(enrich).compile(entries, route=_projects_route())
    assert not result.diagnostics
    projects = {p.slug: p for p in result.page.projects}
    assert set(projects) == {"alice/tool", "bob/tool", "UNCHANGED"}
    assert projects["alice/tool"].title == "Renamed"
    assert projects["alice/tool"].summary == "Public description"
    assert projects["alice/tool"].url == "https://github.com/Alice/Tool"
    assert projects["bob/tool"].title == "Manual" and projects["bob/tool"].summary == ""
    # Explicit internal keys are not route slugs and do not get case-folded.
    assert projects["UNCHANGED"].repository == "Alice/Tool"
    for duplicate in (
        ProjectCatalogEntry(repository="alice/tool"),
        ProjectCatalogEntry(repository="other/repo", slug="alice/tool"),
    ):
        bad = ProjectCompiler().compile(
            [entries[0], duplicate], route=_projects_route()
        )
        assert any(
            d.code == "PROJECT_KEY_DUPLICATE" and d.severity == "error"
            for d in bad.diagnostics
        )


def test_selected_project_defaults_survive_optional_failure_without_secret_leaks() -> (
    None
):
    def fail(repository: str) -> ProjectEnrichment:
        raise RuntimeError("token=secret")

    result = ProjectCompiler(fail).compile(
        [
            ProjectCatalogEntry(
                repository="Alice/Tool",
                fallback_metadata=ProjectFallbackMetadata(stars=7),
            ),
            ProjectCatalogEntry(repository="Bob/Tool", summary=""),
        ],
        route=_projects_route(),
    )
    assert [(p.title, p.summary) for p in result.page.projects] == [
        ("Tool", ""),
        ("Tool", ""),
    ]
    assert result.page.projects[0].stars == 7
    assert all(
        d.severity == "warning" and "secret" not in d.message
        for d in result.diagnostics
    )
    assert len(result.diagnostics) == 2
