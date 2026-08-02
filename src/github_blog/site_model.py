from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from .atom_feed import AtomFeedBuilder
from .blog_archive import BlogArchiveBuilder
from .build_result import Diagnostic
from .config import Settings
from .home_builder import HomeBuilder
from .models.blog_archive import ArchivePage, ArchivePageRoute
from .models.content import ContentCompilationResult, ContentRoute
from .models.home_page import HomeNavigationLink, HomePage, HomeRoute
from .models.projects import ProjectsPage
from .models.site import SiteModel
from .routes import RouteCollisionError, RouteRegistry
from .tag_taxonomy import TagTaxonomyBuilder


class SiteModelBuilder:
    """Assemble one complete SiteModel from one shared RouteRegistry."""

    def __init__(
        self, settings: Settings, route_registry: RouteRegistry | None = None
    ) -> None:
        self.settings = settings
        self.route_registry = route_registry or RouteRegistry(str(settings.site.url))

    def build(
        self,
        content: ContentCompilationResult,
        projects: ProjectsPage,
        *,
        build_start_time: datetime,
    ) -> SiteModel:
        registry = self.route_registry
        diagnostics = list(content.diagnostics)
        self._register_fixed_routes(registry)
        try:
            normalized_content = self._normalize_content(content, registry)
            pages = self._normalize_archives(
                BlogArchiveBuilder(self.settings).build(normalized_content.blogs),
                registry,
            )

            tags_result = TagTaxonomyBuilder(
                self.settings, route_registry=registry
            ).build(normalized_content.blogs)
            diagnostics.extend(tags_result.diagnostics)
            for tag in tags_result.index.tags:
                registry.tag(tag.name)
            for archive in tags_result.archives:
                registry.tag(archive.tag_name)
        except (RouteCollisionError, ValueError) as exc:
            diagnostics.append(
                Diagnostic("error", "ROUTE_COLLISION", str(exc), field="route")
            )
            normalized_content = ContentCompilationResult(
                diagnostics=tuple(diagnostics)
            )
            pages = self._normalize_archives(
                BlogArchiveBuilder(self.settings).build(()), registry
            )
            tags_result = TagTaxonomyBuilder(
                self.settings, route_registry=registry
            ).build(())

        home = HomeBuilder(self.settings).build(normalized_content.blogs)
        try:
            navigation = self._normalize_navigation(home, registry)
        except RouteCollisionError as exc:
            diagnostics.append(
                Diagnostic("error", "ROUTE_COLLISION", str(exc), field="navigation")
            )
            navigation = home.navigation
        home_route = registry.home()
        home = replace(
            home,
            route=HomeRoute(home_route.canonical_path, home_route.output_path),
            canonical_url=home_route.canonical_url,
            navigation=navigation,
        )
        projects = replace(
            projects,
            route=ContentRoute(
                registry.projects().canonical_path, registry.projects().output_path
            ),
            canonical_url=registry.url(registry.projects()),
        )
        feed_result = AtomFeedBuilder(
            self.settings,
            build_start_time=build_start_time,
            route_registry=registry,
        ).build(normalized_content.blogs)
        diagnostics.extend(feed_result.diagnostics)
        feed = feed_result.feed
        return SiteModel(
            home=home,
            blogs=normalized_content.blogs,
            archives=pages,
            ideas=normalized_content.ideas,
            about=normalized_content.about,
            projects=projects,
            tags=tags_result.index,
            tag_archives=tags_result.archives,
            feed=feed,
            routes=registry,
            diagnostics=tuple(diagnostics),
        )

    @staticmethod
    def _register_fixed_routes(registry: RouteRegistry) -> None:
        registry.home()
        registry.ideas()
        registry.about()
        registry.projects()
        registry.tags()
        registry.atom()
        registry.sitemap()
        registry.robots()

    @staticmethod
    def _normalize_archives(
        pages: tuple[ArchivePage, ...], registry: RouteRegistry
    ) -> tuple[ArchivePage, ...]:
        normalized: list[ArchivePage] = []
        for page in pages:
            route = registry.blog_archive(page.page_number)
            previous = (
                registry.blog_archive(page.page_number - 1)
                if page.prev_route is not None
                else None
            )
            following = (
                registry.blog_archive(page.page_number + 1)
                if page.next_route is not None
                else None
            )
            normalized.append(
                replace(
                    page,
                    route=ArchivePageRoute(route.canonical_path, route.output_path),
                    canonical_url=route.canonical_url,
                    prev_route=(
                        ArchivePageRoute(previous.canonical_path, previous.output_path)
                        if previous is not None
                        else None
                    ),
                    next_route=(
                        ArchivePageRoute(
                            following.canonical_path, following.output_path
                        )
                        if following is not None
                        else None
                    ),
                )
            )
        return tuple(normalized)

    @staticmethod
    def _normalize_content(
        content: ContentCompilationResult, registry: RouteRegistry
    ) -> ContentCompilationResult:
        blogs = tuple(
            replace(
                post,
                canonical_path=(
                    route := registry.blog_detail(post.slug)
                ).canonical_path,
                canonical_url=route.canonical_url,
            )
            for post in content.blogs
        )
        ideas = tuple(
            replace(
                idea,
                canonical_path=(
                    route := registry.idea(idea.issue_number)
                ).canonical_path,
                canonical_url=route.canonical_url,
            )
            for idea in content.ideas
        )
        about = content.about
        if about is not None:
            route = registry.about()
            about = replace(
                about,
                canonical_path=route.canonical_path,
                canonical_url=route.canonical_url,
            )
        return replace(content, blogs=blogs, ideas=ideas, about=about)

    @staticmethod
    def _normalize_navigation(
        home: HomePage, registry: RouteRegistry
    ) -> tuple[HomeNavigationLink, ...]:
        # HomePage navigation is a model-owned tuple; internal configured URLs
        # are resolved through the same registry used for page output.
        links = []
        for item in home.navigation:
            if item.url.startswith("/"):
                route = registry.route_for_path(item.url)
                if route is None:
                    raise RouteCollisionError(
                        f"navigation points to an unregistered route: {item.url}"
                    )
                links.append(replace(item, url=route.canonical_path))
            else:
                links.append(item)
        return tuple(links)
