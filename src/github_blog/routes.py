from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlsplit

_KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class RouteCollisionError(ValueError):
    """Raised when a canonical route or output mapping is unsafe or collides."""


@dataclass(frozen=True)
class Route:
    name: str
    canonical_path: str
    output_path: str
    canonical_url: str


class RouteRegistry:
    """The single route/origin registry used by pages, links, and SEO outputs."""

    def __init__(self, origin: str) -> None:
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.path not in ("", "/")
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("RouteRegistry origin must be an HTTPS origin")
        self.origin = f"https://{parsed.netloc}"
        self._routes: dict[str, Route] = {}
        self._canonical_keys: dict[str, Route] = {}
        self._output_paths: dict[str, Route] = {}

    def register(self, name: str, canonical_path: str, output_path: str) -> Route:
        path = self._normalize_path(canonical_path)
        if ".html" in path:
            raise RouteCollisionError("legacy .html routes are not supported")
        if (
            not output_path
            or output_path.startswith("/")
            or ".." in output_path.split("/")
            or (
                output_path.endswith(".html")
                and output_path != "index.html"
                and not output_path.endswith("/index.html")
            )
        ):
            raise RouteCollisionError(f"unsafe output path: {output_path!r}")
        canonical_key = path.casefold()
        existing = self._canonical_keys.get(canonical_key)
        if existing is not None:
            if existing.output_path == output_path:
                self._routes[name] = existing
                return existing
            raise RouteCollisionError(
                f"canonical route collision: {path!r} ({existing.name}, {name})"
            )
        output_existing = self._output_paths.get(output_path.casefold())
        if output_existing is not None:
            raise RouteCollisionError(
                f"output route collision: {output_path!r} ({output_existing.name}, {name})"
            )
        route = Route(name, path, output_path, f"{self.origin}{path}")
        self._routes[name] = route
        self._canonical_keys[canonical_key] = route
        self._output_paths[output_path.casefold()] = route
        return route

    def home(self) -> Route:
        return self.register("home", "/", "index.html")

    def blog_archive(self, page_number: int = 1) -> Route:
        if page_number < 1:
            raise ValueError("blog archive page number must be positive")
        if page_number == 1:
            return self.register("blog", "/blog/", "blog/index.html")
        return self.register(
            f"blog-page-{page_number}",
            f"/blog/page/{page_number}/",
            f"blog/page/{page_number}/index.html",
        )

    def blog_detail(self, slug: str) -> Route:
        if not _KEBAB.fullmatch(slug) or slug == "page":
            raise RouteCollisionError(f"reserved or invalid Blog slug: {slug!r}")
        return self.register(
            f"blog-detail-{slug}",
            f"/blog/{slug}/",
            f"blog/{slug}/index.html",
        )

    def ideas(self) -> Route:
        return self.register("ideas", "/ideas/", "ideas/index.html")

    def idea(self, issue_number: int) -> Route:
        if issue_number <= 0:
            raise ValueError("Idea Issue number must be positive")
        return self.register(
            f"idea-{issue_number}",
            f"/ideas/{issue_number}/",
            f"ideas/{issue_number}/index.html",
        )

    def about(self) -> Route:
        return self.register("about", "/about/", "about/index.html")

    def projects(self) -> Route:
        return self.register("projects", "/projects/", "projects/index.html")

    def tags(self) -> Route:
        return self.register("tags", "/tags/", "tags/index.html")

    def tag(self, tag_key: str) -> Route:
        if not _KEBAB.fullmatch(tag_key) or len(tag_key) > 50:
            raise RouteCollisionError(f"invalid tag key: {tag_key!r}")
        return self.register(
            f"tag-{tag_key}",
            f"/tags/{tag_key}/",
            f"tags/{tag_key}/index.html",
        )

    def atom(self) -> Route:
        return self.register("atom", "/atom.xml", "atom.xml")

    def sitemap(self) -> Route:
        return self.register("sitemap", "/sitemap.xml", "sitemap.xml")

    def robots(self) -> Route:
        return self.register("robots", "/robots.txt", "robots.txt")

    def url(self, route: Route) -> str:
        return route.canonical_url

    def route(self, name: str) -> Route:
        return self._routes[name]

    def route_for_path(self, path: str) -> Route | None:
        return self._canonical_keys.get(self._normalize_path(path).casefold())

    def route_for_url(self, url: str) -> Route | None:
        parsed = urlsplit(url)
        if f"{parsed.scheme}://{parsed.netloc}" != self.origin:
            return None
        return self.route_for_path(parsed.path)

    def route_for_output(self, output_path: str) -> Route | None:
        return self._output_paths.get(output_path.casefold())

    def routes(self) -> tuple[Route, ...]:
        return tuple(self._routes.values())

    def sitemap_routes(self) -> tuple[str, ...]:
        return tuple(
            route.canonical_path
            for route in self._routes.values()
            if route.name not in {"atom", "sitemap", "robots"}
        )

    @staticmethod
    def _normalize_path(path: str) -> str:
        normalized = unicodedata.normalize("NFC", path)
        parsed = urlsplit(normalized)
        if (
            not normalized.startswith("/")
            or "//" in normalized
            or parsed.path != normalized
            or ".." in parsed.path.split("/")
        ):
            raise RouteCollisionError(f"canonical path must be absolute: {path!r}")
        return normalized
