"""Checks on rendered output before it replaces the published site.

``SiteArtifactValidator`` checks integrity only: every Route has its file, no
stray HTML, and internal links and resources resolve. How a Theme writes its
SEO tags is its own concern; ``audit_seo`` reports that as warnings for
``escpe theme check``.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

from .build_result import Diagnostic
from .models.site import SiteModel
from .routes import RouteCollisionError
from .theme import NOT_FOUND_TEMPLATE

_BAD_ESCAPE = re.compile(r"%(?![0-9a-fA-F]{2})")
_UNSAFE_PATH_CHARS = re.compile(
    r"[\x00-\x1f\x7f-\x9f\\\u2028\u2029\u200b\u200c\u200d\ufeff]"
)


def _srcset_urls(value: str) -> list[str]:
    return [part.split()[0] for part in value.split(",") if part.strip()]


class _HTMLProbe(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[tuple[str, str]] = []
        self.canonical: list[str] = []
        self.meta: dict[str, str] = {}
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag in {"a", "link"} and values.get("href"):
            self.references.append((tag, values["href"]))
        if tag in {"script", "img", "source"} and values.get("src"):
            self.references.append((tag, values["src"]))
        for key in ("data-runtime-src", "data-search-index"):
            if tag == "script" and values.get(key):
                self.references.append((tag, values[key]))
        if tag in {"img", "source"} and values.get("srcset"):
            self.references.extend((tag, url) for url in _srcset_urls(values["srcset"]))
        if tag == "link" and values.get("rel", "").casefold() == "canonical":
            self.canonical.append(values.get("href", ""))
        if tag == "meta":
            key = (values.get("property") or values.get("name") or "").casefold()
            if key and "content" in values:
                self.meta[key] = values["content"]
                if key in {"og:image", "twitter:image"}:
                    self.references.append(("meta", values["content"]))
        if tag == "title":
            self._in_title = True

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False


class SiteArtifactValidator:
    """Check rendered files against one SiteModel and its RouteRegistry."""

    def __init__(self, site: SiteModel) -> None:
        self.site = site

    def validate(self, candidate_dir: Path) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        # Exact file names, not case-insensitive filesystem lookups, prove that
        # a public URL exists. Exact membership also rejects traversal paths.
        files = {
            path.relative_to(candidate_dir).as_posix()
            for path in candidate_dir.rglob("*")
            if not path.is_symlink() and path.is_file()
        }
        pages = {
            route.output_path: route.canonical_url
            for route in self.site.routes.routes()
        }
        for output_path in pages:
            if output_path not in files:
                diagnostics.append(
                    _error("MISSING_ROUTE", f"missing page file: {output_path}")
                )
        if NOT_FOUND_TEMPLATE in files:
            # Served for any missing path; resolve its relative links at the root.
            pages[NOT_FOUND_TEMPLATE] = f"{self.site.routes.origin}/"
        for output_path in sorted(
            path for path in files if path.endswith(".html") and path not in pages
        ):
            diagnostics.append(
                _error(
                    "UNREGISTERED_HTML",
                    f"{output_path} is not a page of this site",
                )
            )

        for output_path, base_url in pages.items():
            if output_path not in files or not output_path.endswith(".html"):
                continue
            probe = _read(candidate_dir / output_path, output_path, diagnostics)
            if probe is None:
                continue
            for tag, value in probe.references:
                self._check_reference(
                    output_path, tag, value, base_url, files, diagnostics
                )
        return diagnostics

    def _check_reference(
        self,
        output_path: str,
        tag: str,
        value: str,
        base_url: str,
        files: set[str],
        diagnostics: list[Diagnostic],
    ) -> None:
        try:
            path = self._internal_path(value, base_url)
            if path is None or self.site.routes.route_for_path(path) is not None:
                return
            file = _file_for(path)
        except ValueError, RouteCollisionError:
            diagnostics.append(
                _error("INVALID_INTERNAL_PATH", f"{output_path}: unsafe {tag} URL")
            )
            return
        if file not in files:
            diagnostics.append(
                _error(
                    "BROKEN_INTERNAL_LINK",
                    f"{output_path}: {tag} points to {path}, which is not a page "
                    "or file of this site",
                )
            )

    def _internal_path(self, value: str, base_url: str) -> str | None:
        """Same-origin path for ``value``, or None for fragments and other sites."""
        if not value or value.startswith("#"):
            return None
        # urlsplit can erase controls, and urljoin dot segments: check raw first.
        if _UNSAFE_PATH_CHARS.search(value):
            raise ValueError("unsafe URL characters")
        raw_path = urlsplit(value).path
        resolved = urlsplit(urljoin(base_url, value))
        origin = urlsplit(self.site.routes.origin)
        if (
            resolved.scheme.casefold() != origin.scheme.casefold()
            or resolved.netloc.casefold() != origin.netloc.casefold()
        ):
            return None
        if (
            " " in value
            or "//" in raw_path
            or any(part in (".", "..") for part in raw_path.split("/"))
        ):
            raise ValueError("unsafe URL path segments")
        return resolved.path or "/"


def _file_for(path: str) -> str:
    """Output-relative file name for a URL path, with one strict UTF-8 decode.

    A directory URL such as ``/notes/`` names its ``index.html``.
    """
    if _BAD_ESCAPE.search(path):
        raise ValueError("invalid percent escape")
    if path.endswith("/"):
        path += "index.html"
    parts = [
        unquote(part, errors="strict") for part in path.removeprefix("/").split("/")
    ]
    if any(
        part in ("", ".", "..") or "/" in part or _UNSAFE_PATH_CHARS.search(part)
        for part in parts
    ):
        raise ValueError("unsafe file path component")
    return "/".join(parts)


def audit_seo(site: SiteModel, candidate_dir: Path) -> list[Diagnostic]:
    """Warnings about each page's title, description and canonical tags."""
    diagnostics: list[Diagnostic] = []
    for route in site.routes.sitemap_routes():
        if not route.output_path.endswith(".html"):
            continue
        name = route.output_path
        probe = _read(candidate_dir / name, name, diagnostics)
        if probe is None:
            continue
        if not probe.title.strip():
            diagnostics.append(_warning("SEO_TITLE", f"{name}: has no <title>"))
        if not probe.meta.get("description", "").strip():
            diagnostics.append(
                _warning("SEO_DESCRIPTION", f"{name}: has no meta description")
            )
        if probe.canonical != [route.canonical_url]:
            diagnostics.append(
                _warning(
                    "SEO_CANONICAL",
                    f'{name}: needs one <link rel="canonical" '
                    f'href="{route.canonical_url}">',
                )
            )
        for key in ("og:url", "twitter:url"):
            if key in probe.meta and probe.meta[key] != route.canonical_url:
                diagnostics.append(
                    _warning(
                        "SEO_URL", f"{name}: {key} should be {route.canonical_url}"
                    )
                )
    return diagnostics


def _read(path: Path, name: str, diagnostics: list[Diagnostic]) -> _HTMLProbe | None:
    probe = _HTMLProbe()
    try:
        probe.feed(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        diagnostics.append(_error("HTML_READ_FAILED", f"{name}: {exc}"))
        return None
    return probe


def _error(code: str, message: str) -> Diagnostic:
    return Diagnostic("error", code, message)


def _warning(code: str, message: str) -> Diagnostic:
    return Diagnostic("warning", code, message)
