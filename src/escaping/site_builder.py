from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from urllib.parse import urljoin

from .atom_feed import AtomFeedBuilder
from .blog_archive import build_archives
from .build_result import Diagnostic
from .config import Settings
from .models.content import ContentCompilationResult, ProfileAbout
from .models.projects import Project, ProjectCompilationResult
from .models.site import (
    CommentsMetadata,
    SeoMetadata,
    SiteLink,
    SiteMetadata,
    SiteModel,
    SiteProfile,
    ThemePage,
)
from .routes import Route, RouteCollisionError, RouteRegistry
from .tag_taxonomy import build_tag_taxonomy
from .theme import PageSpec


def register_fixed_routes(routes: RouteRegistry) -> None:
    """Register the compiler's own pages; repeating it is harmless."""
    routes.home()
    routes.blog_archive()
    routes.ideas()
    routes.about()
    routes.projects()
    routes.tags()
    routes.atom()
    routes.sitemap()
    routes.robots()
    routes.search()


class SiteBuilder:
    """Assemble the SiteModel: fixed routes, Theme pages, metadata and feed."""

    def __init__(self, settings: Settings, route_registry: RouteRegistry) -> None:
        self.settings = settings
        self.routes = route_registry

    def build(
        self,
        content: ContentCompilationResult,
        projects: ProjectCompilationResult,
        *,
        pages: Sequence[PageSpec] = (),
        build_start_time: datetime,
    ) -> SiteModel:
        diagnostics = [*content.diagnostics, *projects.diagnostics]
        register_fixed_routes(self.routes)
        archives = build_archives(
            content.blogs, self.settings.paths.page_size, self.routes
        )
        tags = build_tag_taxonomy(content.blogs)
        diagnostics.extend(tags.diagnostics)

        try:
            project_items, theme_pages = self._theme_pages(pages, projects.projects)
        except RouteCollisionError as exc:
            diagnostics.append(
                Diagnostic("error", "ROUTE_COLLISION", str(exc), field="theme.pages")
            )
            project_items, theme_pages = projects.projects, ()

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
            # A configured but missing About is a fatal error; this is only a
            # placeholder then, never published.
            about=content.about
            or ProfileAbout(
                title=self.settings.site.author,
                description=self.settings.profile.bio or self.settings.site.description,
                route=self.routes.about(),
            ),
            projects=project_items,
            tags=tags.tags,
            theme_pages=theme_pages,
            feed=feed.feed,
            routes=self.routes,
            diagnostics=tuple(diagnostics),
            skipped_issues=content.skipped,
        )

    def _theme_pages(
        self, pages: Sequence[PageSpec], projects: tuple[Project, ...]
    ) -> tuple[tuple[Project, ...], tuple[ThemePage, ...]]:
        """Register Theme pages; a project's first detail page becomes its ``page``."""
        items = list(projects)
        theme_pages: list[ThemePage] = []
        for spec in pages:
            if spec.for_each != "projects":
                route = self._theme_route(spec.path, theme_pages)
                theme_pages.append(ThemePage(route, spec.template))
                continue
            for index, project in enumerate(items):
                route = self._theme_route(spec.path_for(project.slug), theme_pages)
                if items[index].page is None:
                    items[index] = replace(project, page=route)
                theme_pages.append(
                    ThemePage(route, spec.template_for(project.slug), items[index])
                )
        return tuple(items), tuple(theme_pages)

    def _theme_route(self, path: str, registered: list[ThemePage]) -> Route:
        """Register one Theme page; two Theme pages may not share a path."""
        route = self.routes.theme_page(path)
        if any(page.route == route for page in registered):
            raise RouteCollisionError(f"two Theme pages use the path {path}")
        return route

    def _navigation(self, *, validate: bool) -> tuple[SiteLink, ...]:
        links = []
        for item in self.settings.site.navigation.items:
            url = item.url
            if validate and url.startswith("/"):
                route = self.routes.route_for_path(url)
                if route is None:
                    raise RouteCollisionError(
                        f"navigation item {item.name} points to {url}, "
                        "which is not a page of this site"
                    )
                url = route.canonical_path
            links.append(SiteLink(item.name, url))
        return tuple(links)

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
