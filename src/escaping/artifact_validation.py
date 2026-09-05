from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import cast
from urllib.parse import urljoin, urlsplit

from .build_result import Diagnostic
from .models.site import SiteModel

_ATOM_NS = "http://www.w3.org/2005/Atom"
_SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


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
            if path.is_file()
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
                output_path, probe.json_ld, route.canonical_url, route.name, diagnostics
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
            parsed = urlsplit(value)
            if value.startswith("#"):
                continue
            if parsed.scheme or parsed.netloc:
                path = self._internal_resource_path(value, current_url)
                if path is None:
                    continue
            elif not value.startswith("/"):
                diagnostics.append(
                    self._error(
                        "RELATIVE_LINK", f"{output_path}: relative {tag} link {value!r}"
                    )
                )
                continue
            else:
                path = parsed.path
            static_prefix = f"{self.site.metadata.theme.asset_path}/"
            if path.startswith(static_prefix):
                if path.lstrip("/") not in actual_files:
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
            path = self._internal_resource_path(value, current_url)
            if path is None:
                continue
            if path.startswith(static_prefix):
                if path.lstrip("/") not in actual_files:
                    diagnostics.append(
                        self._error(
                            "MISSING_ASSET",
                            f"{output_path}: missing {tag} resource {path}",
                        )
                    )
                continue
            if self.site.routes.route_for_path(path) is None:
                diagnostics.append(
                    self._error(
                        "BROKEN_INTERNAL_LINK",
                        f"{output_path}: unregistered {tag} resource {path}",
                    )
                )

    def _internal_resource_path(self, value: str, current_url: str) -> str | None:
        if not value or value.startswith("#"):
            return None
        resolved = urlsplit(urljoin(current_url, value))
        origin = urlsplit(self.site.routes.origin)
        if (
            resolved.scheme.casefold() != origin.scheme.casefold()
            or resolved.netloc.casefold() != origin.netloc.casefold()
        ):
            return None
        return resolved.path or "/"

    def _validate_json_ld(
        self,
        output_path: str,
        scripts: list[str],
        canonical_url: str,
        route_name: str,
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
            urls = self._page_entity_urls(value, route_name)
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
    def _page_entity_urls(value: object, route_name: str) -> list[str]:
        """Check page identities, not author/publisher/isPartOf references.

        Direct document URLs and unreferenced graph roots identify the page.
        Person/Organization/WebSite are supporting graph entities, except for
        About's Person and Home's WebSite. Explicit mainEntity takes precedence
        over references. No remote contexts or schema.org ontology are loaded.
        """
        document = cast(dict[str, object], value) if isinstance(value, dict) else {}
        url = document.get("url")
        urls = [url] if isinstance(url, str) else []
        if "mainEntity" in document:
            entities = document["mainEntity"]
            for entity in entities if isinstance(entities, list) else [entities]:
                urls.extend(SiteArtifactValidator._page_entity_urls(entity, route_name))
        nodes = document.get("@graph", []) if isinstance(value, dict) else value
        if isinstance(nodes, dict):
            nodes = [nodes]
        if not isinstance(nodes, list):
            return urls
        context = document.get("@context")
        contexts = context if isinstance(context, list) else [context]
        # An explicitly referenced graph entity (e.g. citation) is not another
        # page identity just because it is also an Article. mainEntity is the
        # exception: it designates a primary entity rather than a reference.
        referenced: set[str] = set()
        primary: set[str] = set()
        for node in [document, *nodes]:
            if isinstance(node, dict):
                for key, item in node.items():
                    if key == "mainEntity":
                        entities = item if isinstance(item, list) else [item]
                        primary.update(
                            identity
                            for entity in entities
                            if isinstance(entity, dict)
                            for field, identity in entity.items()
                            if field == "@id" and isinstance(identity, str)
                        )
                    elif key not in {"mainEntityOfPage", "@context", "@graph"}:
                        referenced.update(SiteArtifactValidator._reference_ids(item))
        supporting_types = {"Person", "Organization", "WebSite"}
        if route_name == "home":
            supporting_types.remove("WebSite")
        elif route_name == "about":
            supporting_types.remove("Person")
        candidates: list[tuple[str, bool]] = []
        for item in nodes:
            if not isinstance(item, dict):
                continue
            node = cast(dict[str, object], item)
            if "mainEntity" in node:
                entities = node["mainEntity"]
                for entity in entities if isinstance(entities, list) else [entities]:
                    urls.extend(
                        SiteArtifactValidator._page_entity_urls(entity, route_name)
                    )
            identity = node.get("@id")
            explicit_primary = (
                isinstance(identity, str) and identity in primary
            ) or "mainEntityOfPage" in node
            types = node.get("@type", [])
            if isinstance(types, str):
                types = [types]
            if not isinstance(types, list):
                continue
            local_context = node.get("@context")
            local_contexts = (
                local_context if isinstance(local_context, list) else [local_context]
            )
            prefixes = {}
            for context_item in [*contexts, *local_contexts]:
                if isinstance(context_item, dict):
                    for key, definition in context_item.items():
                        if isinstance(definition, dict):
                            definition = cast(dict[str, object], definition).get("@id")
                        if isinstance(key, str):
                            prefixes[key] = definition
            names = set()
            for name in types:
                if not isinstance(name, str):
                    continue
                prefix, separator, local = name.partition(":")
                if separator and prefixes.get(prefix) in (
                    "https://schema.org/",
                    "http://schema.org/",
                ):
                    name = str(prefixes[prefix]) + local
                names.add(
                    name.removeprefix("https://schema.org/").removeprefix(
                        "http://schema.org/"
                    )
                )
            if names and names <= supporting_types and not explicit_primary:
                continue
            url = node.get("url")
            if isinstance(url, str):
                is_reference = (
                    isinstance(identity, str)
                    and identity in referenced
                    and not explicit_primary
                )
                candidates.append((url, is_reference))
        # Cyclic/self references must not make every page identity disappear.
        roots = [url for url, is_reference in candidates if not is_reference]
        return urls + (roots or [url for url, _ in candidates])

    @staticmethod
    def _reference_ids(value: object) -> set[str]:
        if isinstance(value, dict):
            result = set()
            for key, item in value.items():
                if key == "@id" and isinstance(item, str):
                    result.add(item)
                elif key not in {"@context", "@graph"}:
                    result.update(SiteArtifactValidator._reference_ids(item))
            return result
        if isinstance(value, list):
            return {
                identity
                for item in value
                for identity in SiteArtifactValidator._reference_ids(item)
            }
        return set()

    @staticmethod
    def _error(code: str, message: str) -> Diagnostic:
        return Diagnostic("error", code, message)
