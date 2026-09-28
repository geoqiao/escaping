from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import quote, unquote, urlsplit

_KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
#: The path of a site below its origin, such as ``/`` or ``/notes/``.
SITE_PATH = re.compile(r"^/(?:(?!\.\.?/)[A-Za-z0-9._~-]+/)*$")
#: Tag keys may use any Unicode letters or digits, joined by single hyphens.
TAG_KEY = re.compile(r"^[^\W_]+(?:-[^\W_]+)*$")
TAG_KEY_MAX_LENGTH = 50


def with_base(base: str, value: str) -> str:
    """A root-relative address under the site's path: ``/x`` -> ``{base}/x``.

    Anything else (a full URL, a fragment, ``//host``) is returned as is.
    """
    if base and value.startswith("/") and not value.startswith("//"):
        return f"{base}{value}"
    return value


class RouteCollisionError(ValueError):
    """Raised when a canonical route or output mapping is unsafe or collides."""


@dataclass(frozen=True)
class Sections:
    """Where each section lives, from ``pages`` in the Config.

    ``None`` turns a section off. The Blog is always on; Home is always ``/``.
    """

    blog: str = "/blog/"
    ideas: str | None = "/ideas/"
    tags: str | None = "/tags/"
    projects: str | None = "/projects/"
    about: str | None = "/about/"


@dataclass(frozen=True)
class Route:
    """One page address. ``canonical_path`` and ``canonical_url`` are
    percent-encoded; ``output_path`` is the file path relative to the output."""

    name: str
    canonical_path: str
    output_path: str
    canonical_url: str


class RouteRegistry:
    """The single route registry used by pages, links, and SEO outputs.

    Paths given to it are site paths: ``/blog/`` is the Blog wherever the site
    lives. ``canonical_path`` and ``canonical_url`` add the site's own path,
    ``base``, so a site at ``https://alice.github.io/notes/`` publishes its
    Blog at ``/notes/blog/``. Output paths never include ``base``.
    """

    def __init__(self, site_url: str, sections: Sections | None = None) -> None:
        parsed = urlsplit(site_url)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or not SITE_PATH.fullmatch(parsed.path or "/")
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("RouteRegistry site URL must be an HTTPS URL ending in /")
        self.origin = f"https://{parsed.netloc}"
        #: The site's path below the origin without the final /; "" at the root.
        self.base = (parsed.path or "/").removesuffix("/")
        self.sections = sections or Sections()
        self._routes: dict[str, Route] = {}
        self._canonical_keys: dict[str, Route] = {}
        self._output_paths: dict[str, Route] = {}

    def register(self, name: str, canonical_path: str, output_path: str) -> Route:
        path = quote(self._normalize_path(canonical_path), safe="/")
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
        canonical_key = unquote(path).casefold()
        path = f"{self.base}{path}"
        existing = self._canonical_keys.get(canonical_key)
        if existing is not None:
            if (
                existing.name == name
                and existing.canonical_path == path
                and existing.output_path == output_path
            ):
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
        blog = self.sections.blog
        if page_number == 1:
            return self._page("blog", blog)
        return self._page(f"blog-page-{page_number}", f"{blog}page/{page_number}/")

    def blog_detail(self, slug: str) -> Route:
        if not _KEBAB.fullmatch(slug) or slug == "page":
            raise RouteCollisionError(f"reserved or invalid Blog slug: {slug!r}")
        return self._page(f"blog-detail-{slug}", f"{self.sections.blog}{slug}/")

    def ideas(self) -> Route:
        return self._page("ideas", self._section("ideas"))

    def idea(self, issue_number: int) -> Route:
        if issue_number <= 0:
            raise ValueError("Idea Issue number must be positive")
        return self._page(
            f"idea-{issue_number}", f"{self._section('ideas')}{issue_number}/"
        )

    def about(self) -> Route:
        return self._page("about", self._section("about"))

    def projects(self) -> Route:
        return self._page("projects", self._section("projects"))

    def tags(self) -> Route:
        return self._page("tags", self._section("tags"))

    def tag(self, tag_key: str) -> Route:
        if not TAG_KEY.fullmatch(tag_key) or len(tag_key) > TAG_KEY_MAX_LENGTH:
            raise RouteCollisionError(f"invalid tag key: {tag_key!r}")
        return self._page(f"tag-{tag_key}", f"{self._section('tags')}{tag_key}/")

    def extra_page(self, path: str) -> Route:
        """Register a page from ``pages.extra`` at a directory-style path."""
        if not path.startswith("/") or not path.endswith("/"):
            raise RouteCollisionError(f"page path must end with '/': {path!r}")
        return self._page(f"page-{path}", path)

    def _section(self, name: str) -> str:
        path = getattr(self.sections, name)
        if path is None:
            raise RouteCollisionError(f"pages.{name} is off")
        return path

    def _page(self, name: str, path: str) -> Route:
        return self.register(name, path, f"{path[1:]}index.html")

    def atom(self) -> Route:
        return self.register("atom", "/atom.xml", "atom.xml")

    def sitemap(self) -> Route:
        return self.register("sitemap", "/sitemap.xml", "sitemap.xml")

    def robots(self) -> Route:
        return self.register("robots", "/robots.txt", "robots.txt")

    def search(self) -> Route:
        return self.register("search", "/search.json", "search.json")

    def route(self, name: str) -> Route:
        return self._routes[name]

    def get(self, name: str) -> Route | None:
        """The Route called ``name``, or None when that page is off."""
        return self._routes.get(name)

    def route_for_path(self, path: str) -> Route | None:
        """Look up a site path (raw or percent-encoded), case-sensitively."""
        decoded = unicodedata.normalize("NFC", unquote(path))
        self._normalize_path(decoded)
        route = self._canonical_keys.get(decoded.casefold())
        if route is None or unquote(route.canonical_path) != f"{self.base}{decoded}":
            return None
        return route

    def route_for_url(self, url: str) -> Route | None:
        parsed = urlsplit(url)
        if f"{parsed.scheme}://{parsed.netloc}" != self.origin:
            return None
        path = self.site_path(parsed.path)
        return self.route_for_path(path) if path is not None else None

    def site_path(self, url_path: str) -> str | None:
        """The site path of a URL path on this origin; None outside the site."""
        if not self.base:
            return url_path or "/"
        if url_path.startswith(f"{self.base}/"):
            return url_path.removeprefix(self.base)
        return None

    def routes(self) -> tuple[Route, ...]:
        return tuple(self._routes.values())

    def sitemap_routes(self) -> tuple[Route, ...]:
        """Every page Route once, in registration order; no machine files."""
        return tuple(
            route
            for route in self._canonical_keys.values()
            if route.name not in {"atom", "sitemap", "robots", "search"}
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
