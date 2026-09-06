from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

from .build_result import Diagnostic
from .models.content import ProfileAbout
from .models.site import SiteModel

_ATOM_NS = "http://www.w3.org/2005/Atom"
_SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
_BAD_ESCAPE = re.compile(r"%(?![0-9a-fA-F]{2})")
_UNSAFE_PATH_CHARS = re.compile(
    r"[\x00-\x1f\x7f-\x9f\\\u2028\u2029\u200b\u200c\u200d\ufeff]"
)


def _srcset_urls(value: str) -> list[str]:
    urls = []
    for candidate in value.split(","):
        parts = candidate.strip().split()
        if parts:
            urls.append(parts[0])
    return urls


class _HTMLProbe(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.resources: list[tuple[str, str]] = []
        self.canonical: list[str] = []
        self.meta: dict[str, str] = {}
        self.json_ld: list[str] = []
        self._script_type = ""
        self._script_data: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag in {"a", "link"} and values.get("href"):
            self.links.append((tag, values["href"]))
        if tag in {"script", "img", "source"} and values.get("src"):
            self.resources.append((tag, values["src"]))
        if tag == "script" and values.get("data-runtime-src"):
            self.resources.append((tag, values["data-runtime-src"]))
        if tag == "img" and values.get("srcset"):
            self.resources.extend((tag, url) for url in _srcset_urls(values["srcset"]))
        if tag == "link" and values.get("rel", "").casefold() == "canonical":
            self.canonical.append(values.get("href", ""))
        if tag == "meta":
            key = values.get("property") or values.get("name")
            if key and "content" in values:
                self.meta[key.casefold()] = values["content"]
        if tag == "script":
            self._script_type = values.get("type", "")
            self._script_data = []

    def handle_data(self, data: str) -> None:
        if self._script_type == "application/ld+json":
            self._script_data.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._script_type == "application/ld+json":
            self.json_ld.append("".join(self._script_data))
            self._script_type = ""
            self._script_data = []


class SiteArtifactValidator:
    """Validate rendered files against one SiteModel and RouteRegistry."""

    def __init__(self, site: SiteModel) -> None:
        self.site = site

    def validate(self, candidate_dir: Path) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        expected = {route.output_path: route for route in self.site.routes.routes()}
        # File names, not host-filesystem case-insensitive lookups, prove that
        # the public URL exists. Exact membership also rejects traversal paths.
        actual_files = {
            path.relative_to(candidate_dir).as_posix()
            for path in candidate_dir.rglob("*")
            if not path.is_symlink() and path.is_file()
        }
        actual_html = {path for path in actual_files if path.endswith(".html")}
        for output_path in expected:
            if output_path not in actual_files:
                diagnostics.append(
                    self._error(
                        "MISSING_ROUTE", f"missing route artifact: {output_path}"
                    )
                )
        unexpected = sorted(
            actual_html - {path for path in expected if path.endswith(".html")}
        )
        for output_path in unexpected:
            diagnostics.append(
                self._error(
                    "UNREGISTERED_HTML", f"unregistered HTML artifact: {output_path}"
                )
            )

        for output_path, route in expected.items():
            path = candidate_dir / output_path
            if output_path not in actual_files or not output_path.endswith(".html"):
                continue
            probe = _HTMLProbe()
            try:
                text = path.read_text(encoding="utf-8")
                probe.feed(text)
            except (OSError, UnicodeError) as exc:
                diagnostics.append(
                    self._error("HTML_READ_FAILED", f"{output_path}: {exc}")
                )
                continue
            # Body provenance belongs to compilation: only parsed.body becomes
            # body_html, and neither renderer nor validator receives raw Issues.
            # Metadata-like prose cannot establish a front-matter leak.
            self._validate_page_metadata(
                output_path, route.canonical_url, probe, diagnostics
            )
            if route.name == "about":
                self._validate_about_description(output_path, probe, diagnostics)
            self._validate_links(
                output_path,
                route.canonical_url,
                probe.links,
                actual_files,
                diagnostics,
            )
            self._validate_resources(
                output_path,
                route.canonical_url,
                probe.resources,
                actual_files,
                diagnostics,
            )
            self._validate_json_ld(
                output_path, probe.json_ld, route.canonical_url, diagnostics
            )

        self._validate_atom(candidate_dir, diagnostics)
        self._validate_sitemap(candidate_dir, diagnostics)
        self._validate_robots(candidate_dir, diagnostics)
        return diagnostics

    def _validate_page_metadata(
        self,
        output_path: str,
        canonical_url: str,
        probe: _HTMLProbe,
        diagnostics: list[Diagnostic],
    ) -> None:
        if probe.canonical != [canonical_url]:
            diagnostics.append(
                self._error(
                    "CANONICAL_MISMATCH",
                    f"{output_path}: canonical must be {canonical_url}",
                )
            )
        for key in ("og:url", "twitter:url"):
            if probe.meta.get(key) != canonical_url:
                diagnostics.append(
                    self._error(
                        "SEO_URL_MISMATCH",
                        f"{output_path}: {key} must be {canonical_url}",
                    )
                )

    def _validate_about_description(
        self,
        output_path: str,
        probe: _HTMLProbe,
        diagnostics: list[Diagnostic],
    ) -> None:
        expected = self.site.about.description if self.site.about is not None else None
        descriptions = (
            probe.meta.get("description"),
            probe.meta.get("og:description"),
            probe.meta.get("twitter:description"),
        )
        if expected is None or descriptions != (expected, expected, expected):
            diagnostics.append(
                self._error(
                    "ABOUT_DESCRIPTION_MISMATCH",
                    f"{output_path}: description metadata must match About description",
                )
            )

    def _validate_links(
        self,
        output_path: str,
        current_url: str,
        links: list[tuple[str, str]],
        actual_files: set[str],
        diagnostics: list[Diagnostic],
    ) -> None:
        for tag, value in links:
            if value.startswith("#"):
                continue
            try:
                parsed = urlsplit(value)
                path = self._internal_resource_path(value, current_url)
            except ValueError:
                diagnostics.append(
                    self._error(
                        "INVALID_INTERNAL_PATH", f"{output_path}: unsafe {tag} URL path"
                    )
                )
                continue
            if not parsed.scheme and not parsed.netloc and not value.startswith("/"):
                diagnostics.append(
                    self._error(
                        "RELATIVE_LINK", f"{output_path}: relative {tag} link {value!r}"
                    )
                )
                continue
            if path is None:
                continue
            static_prefix = f"{self.site.metadata.theme.asset_path}/"
            if path.startswith(static_prefix):
                self._validate_asset(output_path, path, actual_files, diagnostics)
                continue
            if self.site.routes.route_for_path(path) is None:
                diagnostics.append(
                    self._error(
                        "BROKEN_INTERNAL_LINK",
                        f"{output_path}: unregistered link {path}",
                    )
                )

    def _validate_resources(
        self,
        output_path: str,
        current_url: str,
        resources: list[tuple[str, str]],
        actual_files: set[str],
        diagnostics: list[Diagnostic],
    ) -> None:
        static_prefix = f"{self.site.metadata.theme.asset_path}/"
        for tag, value in resources:
            try:
                path = self._internal_resource_path(value, current_url)
            except ValueError:
                diagnostics.append(
                    self._error(
                        "INVALID_INTERNAL_PATH", f"{output_path}: unsafe {tag} URL path"
                    )
                )
                continue
            if path is None:
                continue
            if path.startswith(static_prefix):
                self._validate_asset(output_path, path, actual_files, diagnostics)
                continue
            if self.site.routes.route_for_path(path) is None:
                diagnostics.append(
                    self._error(
                        "BROKEN_INTERNAL_LINK",
                        f"{output_path}: unregistered {tag} resource {path}",
                    )
                )

    def _validate_asset(
        self,
        output_path: str,
        path: str,
        actual_files: set[str],
        diagnostics: list[Diagnostic],
    ) -> None:
        # Files use one strict UTF-8 URL decode. Never feed decoded names back
        # into URL parsing or RouteRegistry: literal percent names stay literal.
        try:
            if _BAD_ESCAPE.search(path):
                raise ValueError("invalid percent escape")
            parts = [
                unquote(part, errors="strict")
                for part in path.removeprefix("/").split("/")
            ]
            if any(
                part in ("", ".", "..")
                or "/" in part
                or _UNSAFE_PATH_CHARS.search(part)
                for part in parts
            ):
                raise ValueError("unsafe file path component")
        except ValueError:
            diagnostics.append(
                self._error(
                    "INVALID_INTERNAL_PATH",
                    f"{output_path}: unsafe static asset URL path",
                )
            )
            return
        if "/".join(parts) not in actual_files:
            diagnostics.append(
                self._error("MISSING_ASSET", f"{output_path}: missing asset {path}")
            )

    def _internal_resource_path(self, value: str, current_url: str) -> str | None:
        if not value or value.startswith("#"):
            return None
        # urlsplit can erase controls; preserve the raw path for the checks
        # below because urljoin can also erase dot segments.
        if _UNSAFE_PATH_CHARS.search(value):
            raise ValueError("unsafe URL characters")
        raw_path = urlsplit(value).path
        resolved = urlsplit(urljoin(current_url, value))
        origin = urlsplit(self.site.routes.origin)
        if (
            resolved.scheme.casefold() != origin.scheme.casefold()
            or resolved.netloc.casefold() != origin.netloc.casefold()
        ):
            return None
        # Internal file/route references use this explicit safe subset; do not
        # impose local filesystem path rules on unrelated external links.
        if (
            " " in value
            or "//" in raw_path
            or any(part in (".", "..") for part in raw_path.split("/"))
        ):
            raise ValueError("unsafe URL path segments")
        return resolved.path or "/"

    def _validate_json_ld(
        self,
        output_path: str,
        scripts: list[str],
        canonical_url: str,
        diagnostics: list[Diagnostic],
    ) -> None:
        for script in scripts:
            try:
                value = json.loads(script)
            except json.JSONDecodeError:
                diagnostics.append(
                    self._error("INVALID_JSON_LD", f"{output_path}: invalid JSON-LD")
                )
                continue
            # Theme contract, not general JSON-LD interpretation: a legacy
            # document's literal url, or one exact canonical @id in @graph.
            if not isinstance(value, dict) or (
                "@graph" in value
                and (
                    not isinstance(value["@graph"], list)
                    or not all(isinstance(node, dict) for node in value["@graph"])
                )
            ):
                diagnostics.append(
                    self._error(
                        "INVALID_JSON_LD",
                        f"{output_path}: JSON-LD requires an object with optional @graph array of objects",
                    )
                )
                continue
            entities = [value]
            if "@graph" in value:
                primary = [
                    node for node in value["@graph"] if node.get("@id") == canonical_url
                ]
                if len(primary) != 1:
                    diagnostics.append(
                        self._error(
                            "JSON_LD_PAGE_IDENTITY",
                            f"{output_path}: @graph requires exactly one node with @id equal to canonical",
                        )
                    )
                    continue
                entities.extend(primary)
            if (
                isinstance(self.site.about, ProfileAbout)
                and canonical_url == self.site.about.canonical_url
                and (
                    entities[-1].get("@type") not in ("AboutPage", "ProfilePage")
                    or any(
                        key in entities[-1] for key in ("datePublished", "dateModified")
                    )
                )
            ):
                diagnostics.append(
                    self._error(
                        "PROFILE_ABOUT_IDENTITY",
                        f"{output_path}: Profile About requires a non-Article page identity without Issue dates",
                    )
                )
            if any(
                "url" in entity
                and (
                    not isinstance(entity["url"], str) or entity["url"] != canonical_url
                )
                for entity in entities
            ):
                diagnostics.append(
                    self._error(
                        "JSON_LD_URL_MISMATCH",
                        f"{output_path}: provided JSON-LD page url must be a canonical string",
                    )
                )

    def _validate_atom(
        self, candidate_dir: Path, diagnostics: list[Diagnostic]
    ) -> None:
        path = candidate_dir / "atom.xml"
        if not path.is_file():
            diagnostics.append(self._error("MISSING_ATOM", "atom.xml is missing"))
            return
        try:
            root = ET.fromstring(path.read_bytes())  # noqa: S314 - stdlib parser does not resolve external entities
        except ET.ParseError as exc:
            diagnostics.append(self._error("INVALID_ATOM", str(exc)))
            return
        self_url = next(
            (
                element.attrib.get("href")
                for element in root.findall(f"{{{_ATOM_NS}}}link")
                if element.attrib.get("rel") == "self"
            ),
            None,
        )
        if self_url != self.site.routes.url(self.site.routes.route("atom")):
            diagnostics.append(
                self._error("ATOM_SELF_MISMATCH", "Atom self link is not registered")
            )
        for entry in root.findall(f"{{{_ATOM_NS}}}entry"):
            link = entry.find(f"{{{_ATOM_NS}}}link")
            if (
                link is None
                or self.site.routes.route_for_url(link.attrib.get("href", "")) is None
            ):
                diagnostics.append(
                    self._error("ATOM_ENTRY_ROUTE", "Atom entry link is not registered")
                )

    def _validate_sitemap(
        self, candidate_dir: Path, diagnostics: list[Diagnostic]
    ) -> None:
        path = candidate_dir / "sitemap.xml"
        if not path.is_file():
            diagnostics.append(self._error("MISSING_SITEMAP", "sitemap.xml is missing"))
            return
        try:
            root = ET.fromstring(path.read_bytes())  # noqa: S314 - stdlib parser does not resolve external entities
        except ET.ParseError as exc:
            diagnostics.append(self._error("INVALID_SITEMAP", str(exc)))
            return
        actual = {
            element.text
            for element in root.findall(f"{{{_SITEMAP_NS}}}url/{{{_SITEMAP_NS}}}loc")
        }
        expected = {
            f"{self.site.routes.origin}{path}"
            for path in self.site.routes.sitemap_routes()
        }
        if actual != expected:
            diagnostics.append(
                self._error(
                    "SITEMAP_MISMATCH", "sitemap membership differs from RouteRegistry"
                )
            )

    def _validate_robots(
        self, candidate_dir: Path, diagnostics: list[Diagnostic]
    ) -> None:
        path = candidate_dir / "robots.txt"
        if not path.is_file():
            diagnostics.append(self._error("MISSING_ROBOTS", "robots.txt is missing"))
            return
        expected = self.site.routes.url(self.site.routes.route("sitemap"))
        if f"Sitemap: {expected}" not in path.read_text(encoding="utf-8"):
            diagnostics.append(
                self._error(
                    "ROBOTS_MISMATCH",
                    "robots.txt does not reference registered sitemap",
                )
            )

    @staticmethod
    def _error(code: str, message: str) -> Diagnostic:
        return Diagnostic("error", code, message)
