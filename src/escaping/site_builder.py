from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from html import escape
from urllib.parse import urljoin

from .atom_feed import AtomFeedBuilder
from .blog_archive import build_archives
from .build_result import Diagnostic
from .config import ExtraPageConfig, Settings
from .models.content import AboutPage, ContentCompilationResult, ProfileAbout
from .models.projects import Project, ProjectCompilationResult
from .models.site import (
    CommentsMetadata,
    ExtraPage,
    SeoMetadata,
    SiteLink,
    SiteMetadata,
    SiteModel,
    SiteProfile,
)
from .routes import Route, RouteCollisionError, RouteRegistry
from .tag_taxonomy import build_tag_taxonomy


def register_fixed_routes(routes: RouteRegistry) -> None:
    """Register Home, the sections that are on and the machine files.

    Repeating it is harmless.
    """
    routes.home()
    routes.blog_archive()
    sections = routes.sections
    for name, register in (
        ("ideas", routes.ideas),
        ("about", routes.about),
        ("projects", routes.projects),
        ("tags", routes.tags),
    ):
        if getattr(sections, name) is not None:
            register()
    routes.atom()
    routes.sitemap()
    routes.robots()
    routes.search()


class SiteBuilder:
    """Assemble the SiteModel: fixed routes, extra pages, metadata and feed."""

    def __init__(self, settings: Settings, route_registry: RouteRegistry) -> None:
        self.settings = settings
        self.routes = route_registry

    def build(
        self,
        content: ContentCompilationResult,
        projects: ProjectCompilationResult,
        *,
        pages: Sequence[ExtraPageConfig] = (),
        build_start_time: datetime,
    ) -> SiteModel:
        diagnostics = [*content.diagnostics, *projects.diagnostics]
        register_fixed_routes(self.routes)
        archives = build_archives(
            content.blogs, self.settings.paths.page_size, self.routes
        )
        sections = self.routes.sections
        tags = build_tag_taxonomy(content.blogs) if sections.tags else None
        if tags is not None:
            diagnostics.extend(tags.diagnostics)

        try:
            project_items, extra_pages = self._extra_pages(pages, projects.projects)
        except RouteCollisionError as exc:
            diagnostics.append(
                Diagnostic("error", "ROUTE_COLLISION", str(exc), field="pages.extra")
            )
            project_items, extra_pages = projects.projects, ()

        try:
            navigation = self._navigation(validate=True)
        except RouteCollisionError as exc:
            diagnostics.append(
                Diagnostic(
                    "error", "ROUTE_COLLISION", str(exc), field="site.navigation"
                )
            )
            navigation = self._navigation(validate=False)
        metadata = self._metadata(navigation)

        feed = AtomFeedBuilder(
            metadata, build_start_time=build_start_time, route_registry=self.routes
        ).build(content.blogs)
        diagnostics.extend(feed.diagnostics)
        return SiteModel(
            metadata=metadata,
            blogs=content.blogs,
            archives=archives,
            ideas=content.ideas,
            about=self._about(content) if sections.about else None,
            projects=project_items,
            tags=tags.tags if tags is not None else (),
            extra_pages=extra_pages,
            feed=feed.feed,
            routes=self.routes,
            diagnostics=tuple(diagnostics),
            skipped_issues=content.skipped,
        )

    def _about(self, content: ContentCompilationResult) -> AboutPage | ProfileAbout:
        # A configured but missing About is a fatal error; the Profile About is
        # then only a placeholder, never published.
        if content.about is not None:
            return content.about
        bio = self.settings.profile.bio
        return ProfileAbout(
            title=self.settings.site.author,
            description=bio or self.settings.site.description,
            body_html=f"<p>{escape(bio)}</p>" if bio else "",
            route=self.routes.about(),
        )

    def _extra_pages(
        self, pages: Sequence[ExtraPageConfig], projects: tuple[Project, ...]
    ) -> tuple[tuple[Project, ...], tuple[ExtraPage, ...]]:
        """Register extra pages; a project's first detail page becomes its ``page``."""
        items = list(projects)
        extra_pages: list[ExtraPage] = []
        for spec in pages:
            if spec.for_each != "projects":
                route = self._extra_route(spec.path, extra_pages)
                extra_pages.append(ExtraPage(route, spec.template))
                continue
            for index, project in enumerate(items):
                route = self._extra_route(spec.path_for(project.slug), extra_pages)
                if items[index].page is None:
                    items[index] = replace(project, page=route)
                extra_pages.append(
                    ExtraPage(route, spec.template_for(project.slug), items[index])
                )
        return tuple(items), tuple(extra_pages)

    def _extra_route(self, path: str, registered: list[ExtraPage]) -> Route:
        """Register one extra page; two extra pages may not share a path."""
        route = self.routes.extra_page(path)
        if any(page.route == route for page in registered):
            raise RouteCollisionError(f"two extra pages use the path {path}")
        return route

    def _navigation(self, *, validate: bool) -> tuple[SiteLink, ...]:
        links = []
        for item in self.settings.navigation:
            url = item.url
            if validate and url.startswith("/"):
                route = self.routes.route_for_path(url)
                if route is None:
                    raise RouteCollisionError(
                        f"navigation item {item.name} points to {url}, "
                        f"which is not a page of this site{self._off_hint(url)}"
                    )
                url = route.canonical_path
            links.append(SiteLink(item.name, url))
        return tuple(links)

    def _off_hint(self, url: str) -> str:
        sections = self.routes.sections
        for name in ("ideas", "tags", "projects", "about"):
            if url == f"/{name}/" and getattr(sections, name) is None:
                return f" (pages.{name} is false)"
        return ""

    def _metadata(self, navigation: tuple[SiteLink, ...]) -> SiteMetadata:
        settings = self.settings
        social_image = settings.seo.social_image
        if social_image.startswith("/"):
            social_image = urljoin(f"{self.routes.origin}/", social_image)
        return SiteMetadata(
            title=settings.site.title,
            author=settings.site.author,
            description=settings.site.description,
            language=settings.site.language,
            repo=settings.github.repo,
            navigation=navigation,
            profile=SiteProfile(
                avatar=settings.profile.avatar,
                bio=settings.profile.bio,
                links=tuple(
                    SiteLink(link.name, link.url) for link in settings.profile.links
                ),
            ),
            comments=CommentsMetadata(
                enabled=settings.comments.enabled,
                repo=settings.comments.repo or settings.github.repo,
            ),
            seo=SeoMetadata(
                google_search_console=settings.seo.google_search_console,
                social_image=social_image,
                social_image_alt=settings.seo.social_image_alt,
            ),
        )
