from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from .build_result import Diagnostic
from .config import Settings
from .models.site import SiteModel

_ATOM_NS = "http://www.w3.org/2005/Atom"
_SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


class _HTMLProbe(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.canonical: list[str] = []
        self.meta: dict[str, str] = {}
        self.json_ld: list[str] = []
        self._script_type = ""
        self._script_data: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag in {"a", "link"} and values.get("href"):
            self.links.append((tag, values["href"]))
        if tag == "link" and values.get("rel", "").casefold() == "canonical":
            self.canonical.append(values.get("href", ""))
        if tag == "meta":
            key = values.get("property") or values.get("name")
            if key and values.get("content"):
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

    def __init__(self, settings: Settings, site: SiteModel) -> None:
        self.settings = settings
        self.site = site

    def validate(self, candidate_dir: Path) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        expected = {route.output_path: route for route in self.site.routes.routes()}
        actual_html = {
            str(path.relative_to(candidate_dir))
            for path in candidate_dir.rglob("*.html")
            if path.is_file()
        }
        for output_path in expected:
            if (
                output_path.endswith(".html")
                and not (candidate_dir / output_path).is_file()
            ):
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
            if not path.is_file() or not output_path.endswith(".html"):
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
            if "created_date:" in text or "slug:" in text or "\n---\n" in text:
                diagnostics.append(
                    self._error(
                        "FRONT_MATTER_LEAK", f"front matter leaked into {output_path}"
                    )
                )
            self._validate_page_metadata(
                output_path, route.canonical_url, probe, diagnostics
            )
            self._validate_links(output_path, probe.links, candidate_dir, diagnostics)
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

    def _validate_links(
        self,
        output_path: str,
        links: list[tuple[str, str]],
        candidate_dir: Path,
        diagnostics: list[Diagnostic],
    ) -> None:
        for tag, value in links:
            parsed = urlsplit(value)
            if parsed.scheme or parsed.netloc or value.startswith("#"):
                continue
            if not value.startswith("/"):
                diagnostics.append(
                    self._error(
                        "RELATIVE_LINK", f"{output_path}: relative {tag} link {value!r}"
                    )
                )
                continue
            path = parsed.path
            static_prefix = f"/templates/{self.settings.paths.theme}/"
            if path.startswith(static_prefix):
                asset = candidate_dir / path.lstrip("/")
                if not asset.is_file():
                    diagnostics.append(
                        self._error(
                            "MISSING_ASSET", f"{output_path}: missing asset {path}"
                        )
                    )
                continue
            if self.site.routes.route_for_path(path) is None:
                diagnostics.append(
                    self._error(
                        "BROKEN_INTERNAL_LINK",
                        f"{output_path}: unregistered link {path}",
                    )
                )

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
            urls = self._collect_urls(value)
            if any(url != canonical_url for url in urls):
                diagnostics.append(
                    self._error(
                        "JSON_LD_URL_MISMATCH",
                        f"{output_path}: JSON-LD URL differs from canonical",
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
    def _collect_urls(value: object) -> list[str]:
        if isinstance(value, dict):
            direct = [
                item
                for key, item in value.items()
                if key == "url" and isinstance(item, str)
            ]
            nested = [
                url
                for item in value.values()
                for url in SiteArtifactValidator._collect_urls(item)
            ]
            return direct + nested
        if isinstance(value, list):
            return [
                url
                for item in value
                for url in SiteArtifactValidator._collect_urls(item)
            ]
        return []

    @staticmethod
    def _error(code: str, message: str) -> Diagnostic:
        return Diagnostic("error", code, message)
