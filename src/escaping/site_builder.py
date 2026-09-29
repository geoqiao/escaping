from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from html import escape
from urllib.parse import quote

from .build_result import Diagnostic
from .config import ExtraPageConfig, Settings
from .models.blog_post import BlogPost
from .models.content import AboutPage, ContentCompilationResult, ProfileAbout
from .models.projects import Project, ProjectCompilationResult
from .models.site import (
    ArchivePage,
    CommentsMetadata,
    ExtraPage,
    Redirect,
    SeoMetadata,
    SiteLink,
    SiteMetadata,
    SiteModel,
    SiteProfile,
    Tag,
)
from .routes import Route, RouteCollisionError, RouteRegistry, with_base


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
    if not routes.base:
        # Crawlers read robots.txt only at the root of a host.
        routes.robots()
    routes.search()


def _archives(
    posts: Sequence[BlogPost], page_size: int, routes: RouteRegistry
) -> tuple[ArchivePage, ...]:
    """Paginate the Blog archive; an empty Blog has one page."""
    slices = [
        tuple(posts[start : start + page_size])
        for start in range(0, len(posts), page_size)
    ] or [()]
    total = len(slices)
    return tuple(
        ArchivePage(
            page_number=number,
            total_pages=total,
            route=routes.blog_archive(number),
            prev_route=routes.blog_archive(number - 1) if number > 1 else None,
            next_route=routes.blog_archive(number + 1) if number < total else None,
            posts=page_posts,
        )
        for number, page_posts in enumerate(slices, start=1)
    )


def _tags(posts: Sequence[BlogPost]) -> tuple[Tag, ...]:
    """Group Blog posts by tag key; the newest post's spelling names the tag."""
    grouped: dict[str, list[BlogPost]] = {}
    for post in posts:
        for tag in post.tags:
            grouped.setdefault(tag.key, []).append(post)
    tags = []
    for key in sorted(grouped):
        members = grouped[key]
        first = next(tag for tag in members[0].tags if tag.key == key)
        if first.route is None:
            raise ValueError("tag pages are off; there is no taxonomy to build")
        tags.append(Tag(first.name, key, first.route, tuple(members)))
    return tuple(tags)


class SiteBuilder:
    """Assemble the SiteModel: fixed routes, extra pages and metadata."""

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
        sections = self.routes.sections

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
        redirects = self._redirects(diagnostics)
        return SiteModel(
            metadata=self._metadata(navigation),
            blogs=content.blogs,
            archives=_archives(
                content.blogs, self.settings.paths.page_size, self.routes
            ),
            ideas=content.ideas,
            about=self._about(content) if sections.about else None,
            projects=project_items,
            tags=_tags(content.blogs) if sections.tags else (),
            extra_pages=extra_pages,
            routes=self.routes,
            build_start_time=build_start_time,
            redirects=redirects,
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

    def _redirects(self, diagnostics: list[Diagnostic]) -> tuple[Redirect, ...]:
        """Redirects to pages that exist; a page always wins over a redirect.

        A redirect to another old address follows it to the page. One that
        cannot be written is left out with a warning, because the pages it
        depends on come from Issues.
        """
        configured = self.settings.redirects
        outputs = {route.output_path.casefold() for route in self.routes.routes()}
        redirects = []
        for path, target in configured.items():
            output = f"{path[1:]}index.html" if path.endswith("/") else path[1:]
            route = self.routes.route_for_path(target)
            while route is None and target in configured:
                target = configured[target]
                route = self.routes.route_for_path(target)
            if output.casefold() in outputs:
                problem = "is a page of this site now"
            elif route is None:
                problem = (
                    f"points to {configured[path]}, which is not a page of this site"
                )
            else:
                url = f"{self.routes.origin}{self.routes.base}{quote(path, safe='/')}"
                redirects.append(Redirect(path, output, url, route))
                continue
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "REDIRECT_LEFT_OUT",
                    f"redirects: {path} {problem}; the redirect is left out",
                    field="redirects",
                )
            )
        return tuple(redirects)

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
            else:
                url = with_base(self.routes.base, url)
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
        base = self.routes.base
        social_image = with_base(base, settings.seo.social_image)
        if social_image.startswith("/"):
            social_image = f"{self.routes.origin}{social_image}"
        return SiteMetadata(
            title=settings.site.title,
            author=settings.site.author,
            description=settings.site.description,
            language=settings.site.language,
            repo=settings.github.repo,
            navigation=navigation,
            profile=SiteProfile(
                avatar=with_base(base, settings.profile.avatar),
                bio=settings.profile.bio,
                links=tuple(
                    SiteLink(link.name, with_base(base, link.url))
                    for link in settings.profile.links
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
