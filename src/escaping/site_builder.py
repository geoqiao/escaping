from __future__ import annotations

from datetime import datetime

from .atom_feed import AtomFeedBuilder
from .blog_archive import build_archives
from .build_result import Diagnostic
from .config import BuiltinThemeConfig, Settings
from .home_builder import build_home
from .models.content import ContentCompilationResult
from .models.projects import ProjectCompilationResult, ProjectsPage
from .models.site import (
    BrandingMetadata,
    CommentsMetadata,
    IdeasPage,
    SiteLink,
    SiteMetadata,
    SiteModel,
    SiteProfile,
    ThemeMetadata,
)
from .routes import RouteCollisionError, RouteRegistry
from .tag_taxonomy import build_tag_taxonomy

_BUILTIN_THEME_UNRENDERED_FIELDS = {
    "geoqiao.me": ("site.thesis", "profile.tagline", "profile.bio"),
    "Escape1": ("site.thesis", "profile.tagline"),
    "Escape2": ("site.thesis", "profile.tagline"),
}


class SiteBuilder:
    """Build the complete SiteModel by coordinating modular page builders."""

    def __init__(
        self, settings: Settings, route_registry: RouteRegistry | None = None
    ) -> None:
        self.settings = settings
        self.routes = route_registry or RouteRegistry(str(settings.site.url))

    def build(
        self,
        content: ContentCompilationResult,
        projects: ProjectCompilationResult,
        *,
        build_start_time: datetime,
    ) -> SiteModel:
        diagnostics = [*content.diagnostics, *projects.diagnostics]
        diagnostics.extend(self._theme_contract_diagnostics())
        projects_page = projects.page
        self._register_fixed_routes()

        try:
            self._require_registered_content(content, projects_page)
            archives = build_archives(
                content.blogs, self.settings.paths.page_size, self.routes
            )
            tags_result = build_tag_taxonomy(content.blogs, self.routes)
            diagnostics.extend(tags_result.diagnostics)
        except (RouteCollisionError, ValueError) as exc:
            diagnostics.append(
                Diagnostic("error", "ROUTE_COLLISION", str(exc), field="route")
            )
            archives = build_archives((), self.settings.paths.page_size, self.routes)
            tags_result = build_tag_taxonomy((), self.routes)

        try:
            metadata = self._build_metadata(validate_navigation=True)
        except RouteCollisionError as exc:
            diagnostics.append(
                Diagnostic("error", "ROUTE_COLLISION", str(exc), field="navigation")
            )
            metadata = self._build_metadata(validate_navigation=False)

        home = build_home(content.blogs, self.routes)
        feed_result = AtomFeedBuilder(
            metadata,
            build_start_time=build_start_time,
            route_registry=self.routes,
        ).build(content.blogs)
        diagnostics.extend(feed_result.diagnostics)
        return SiteModel(
            metadata=metadata,
            home=home,
            blogs=content.blogs,
            archives=archives,
            ideas_page=IdeasPage(self.routes.ideas(), content.ideas),
            ideas=content.ideas,
            about=content.about,
            projects=projects_page,
            tags=tags_result.index,
            tag_archives=tags_result.archives,
            feed=feed_result.feed,
            routes=self.routes,
            diagnostics=tuple(diagnostics),
        )

    def _theme_contract_diagnostics(self) -> tuple[Diagnostic, ...]:
        theme = self.settings.theme
        if not isinstance(theme, BuiltinThemeConfig):
            return ()
        configured_values = {
            "site.thesis": self.settings.site.thesis,
            "profile.tagline": self.settings.profile.tagline,
            "profile.bio": self.settings.profile.bio,
        }
        return tuple(
            Diagnostic(
                "warning",
                "THEME_FIELD_NOT_RENDERED",
                f"Built-in Theme {theme.name!r} does not render {field}; "
                "the value remains available to compatible local Themes.",
                field=field,
            )
            for field in _BUILTIN_THEME_UNRENDERED_FIELDS.get(theme.name, ())
            if configured_values[field]
        )

    def _register_fixed_routes(self) -> None:
        self.routes.home()
        self.routes.ideas()
        self.routes.about()
        self.routes.projects()
        self.routes.tags()
        self.routes.atom()
        self.routes.sitemap()
        self.routes.robots()

    def _build_metadata(self, *, validate_navigation: bool) -> SiteMetadata:
        settings = self.settings
        theme_path = f"/templates/{settings.theme.name}"
        navigation: list[SiteLink] = []
        for item in settings.site.navigation.items:
            url = item.url
            if validate_navigation and url.startswith("/"):
                route = self.routes.route_for_path(url)
                if route is None:
                    raise RouteCollisionError(
                        f"navigation points to an unregistered route: {url}"
                    )
                url = route.canonical_path
            navigation.append(SiteLink(item.name, url))

        return SiteMetadata(
            title=settings.site.title,
            author=settings.site.author,
            description=settings.site.description,
            language=settings.site.language,
            github_name=settings.github.username,
            github_repo=settings.github.repo,
            navigation=tuple(navigation),
            thesis=tuple(settings.site.thesis),
            profile=SiteProfile(
                avatar=settings.profile.avatar,
                tagline=settings.profile.tagline,
                bio=settings.profile.bio,
                links=tuple(
                    SiteLink(link.name, link.url) for link in settings.profile.links
                ),
            ),
            branding=BrandingMetadata(
                show_powered_by=settings.branding.show_powered_by,
                powered_by_text=settings.branding.powered_by_text,
                powered_by_url=settings.branding.powered_by_url,
                source_link_url=settings.branding.source_link_url,
            ),
            comments=CommentsMetadata(
                repo=settings.comments.repo or settings.github.repo,
                theme=settings.comments.theme,
                theme_mode=settings.comments.theme_mode,
            ),
            google_search_verification=settings.seo.google_search_console,
            theme=ThemeMetadata(
                name=settings.theme.name,
                asset_path=theme_path,
                favicon_url=(
                    f"{self.routes.origin}{theme_path}/static/images/favicon.png"
                ),
            ),
        )

    def _require_registered_content(
        self, content: ContentCompilationResult, projects: ProjectsPage
    ) -> None:
        page_routes = [page.route for page in (*content.blogs, *content.ideas)]
        if content.about is not None:
            page_routes.append(content.about.route)
        for route in page_routes:
            if self.routes.route_for_path(route.canonical_path) is not route:
                raise RouteCollisionError(
                    f"page Route does not belong to the shared registry: {route.name}"
                )
        if (
            self.routes.route_for_path(projects.route.canonical_path)
            is not projects.route
        ):
            raise RouteCollisionError(
                "Projects Route does not belong to the shared registry"
            )
