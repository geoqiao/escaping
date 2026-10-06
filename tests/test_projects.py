from __future__ import annotations

from escaping_site.config import Link, ProjectCatalogEntry, ProjectFallbackMetadata
from escaping_site.models.projects import ProjectLink
from escaping_site.projects import ProjectCompiler, ProjectEnrichment


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


def test_projects_sort_by_order_then_slug_and_link_to_website_or_github() -> None:
    result = ProjectCompiler().compile(
        [
            _entry("z", order=1, featured=True),
            _entry("a", order=1, featured=True),
            _entry("first", order=0),
            ProjectCatalogEntry(
                website="https://example.org/",
                slug="site",
                title="Site",
                order=2,
                image="/assets/images/site.webp",
                links=[Link(name="Demo", url="https://demo.example.org/")],
            ),
        ]
    )
    projects = {project.slug: project for project in result.projects}
    assert list(projects) == ["first", "a", "z", "site"]
    assert projects["first"].url == "https://github.com/geoqiao/first"
    assert projects["first"].repository_url == "https://github.com/geoqiao/first"
    assert projects["a"].featured and not projects["first"].featured
    site = projects["site"]
    assert (site.url, site.repository, site.repository_url) == (
        "https://example.org/",
        "",
        "",
    )
    assert site.image == "/assets/images/site.webp"
    assert site.links == (ProjectLink("Demo", "https://demo.example.org/"),)
    assert all(project.page is None for project in result.projects)


def test_enrichment_fills_defaults_but_explicit_values_win() -> None:
    calls: list[str] = []

    def enrich(repository: str) -> ProjectEnrichment:
        calls.append(repository)
        return ProjectEnrichment(
            name="Renamed",
            description="Public description",
            stars=12,
            language="Rust",
        )

    result = ProjectCompiler(enrich).compile(
        [
            ProjectCatalogEntry(repository="Alice/Tool"),
            ProjectCatalogEntry(
                repository="alice/tool", slug="manual", title="Manual", summary=""
            ),
            ProjectCatalogEntry(website="https://example.org/", slug="w", title="W"),
        ]
    )
    assert not result.diagnostics
    projects = {project.slug: project for project in result.projects}
    assert (projects["tool"].title, projects["tool"].summary) == (
        "Renamed",
        "Public description",
    )
    assert (projects["manual"].title, projects["manual"].summary) == ("Manual", "")
    assert projects["manual"].stars == 12 and projects["manual"].language == "Rust"
    assert projects["w"].stars is None
    # One lookup per repository; a website-only project has nothing to enrich.
    assert len(calls) == 1


def test_enrichment_failure_uses_fallback_and_warns_without_leaking_errors() -> None:
    fallback = ProjectFallbackMetadata(
        stars=7, forks=2, language="Python", topics=["tools"]
    )

    def enrich(repository: str) -> ProjectEnrichment:
        if repository.endswith("live"):
            return ProjectEnrichment(
                stars=10, forks=3, language="Rust", topics=("cli",)
            )
        raise RuntimeError("token=secret")

    result = ProjectCompiler(enrich).compile(
        [
            _entry("fallback", fallback=fallback),
            _entry("live"),
            ProjectCatalogEntry(repository="Bob/Tool", summary=""),
        ]
    )
    projects = {project.slug: project for project in result.projects}
    assert projects["fallback"].stars == 7
    assert projects["fallback"].topics == ("tools",)
    assert projects["live"].stars == 10 and projects["live"].language == "Rust"
    assert (projects["tool"].title, projects["tool"].stars) == ("Tool", None)
    assert [(d.severity, d.code, d.field) for d in result.diagnostics] == [
        ("warning", "PROJECT_ENRICHMENT_FAILED", "projects.fallback"),
        ("warning", "PROJECT_ENRICHMENT_FAILED", "projects.tool"),
    ]
    assert "geoqiao/fallback" in result.diagnostics[0].message
    assert all("secret" not in d.message for d in result.diagnostics)
