"""Render one SiteModel through one loaded Theme.

Templates receive exactly four names: ``site``, ``page``, ``theme`` (resolved
options) and ``t`` (UI strings). See docs/themes/authoring.md.
"""

from __future__ import annotations

import json
import shutil
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from jinja2 import Environment

from ..atom_feed import render_atom_xml
from ..build_result import Diagnostic
from ..models.blog_archive import ArchivePage
from ..models.blog_post import BlogPost, blog_post_sort_key
from ..models.content import AboutPage, Idea, ProfileAbout
from ..models.site import SiteModel
from ..routes import Route
from ..search import build_search_index
from ..theme import (
    NOT_FOUND_TEMPLATE,
    SHARED_ASSET_DIR,
    LoadedTheme,
)

#: Scripts shared by every Theme, published at ``/assets/escaping/``.
SHARED_STATIC = Path(__file__).resolve().parent.parent / "static"

_SITE_ROUTES = ("home", "blog", "ideas", "about", "projects", "tags", "atom", "search")
#: Every page has these names; the ones that do not apply are None.
_PAGE_FIELDS = ("item", "items", "pagination", "newer", "older", "tag", "project")


@dataclass(frozen=True)
class RenderedSite:
    """Output-relative path -> text, plus warnings found while rendering."""

    files: dict[str, str]
    diagnostics: tuple[Diagnostic, ...] = ()


class RenderService:
    """Render every page and machine-readable file for one SiteModel."""

    def __init__(self, theme: LoadedTheme, options: SimpleNamespace) -> None:
        self.theme = theme
        self.options = options
        self.env: Environment = theme.environment()

    def copy_assets(self, output_dir: Path) -> None:
        """Theme static files to ``/assets/``, shared scripts to ``/assets/escaping/``."""
        self.theme.copy_static(output_dir)
        shutil.copytree(
            SHARED_STATIC,
            output_dir / "assets" / SHARED_ASSET_DIR,
            ignore=shutil.ignore_patterns(".*", "__pycache__"),
            dirs_exist_ok=True,
        )

    def render_site(self, site: SiteModel) -> RenderedSite:
        diagnostics: list[Diagnostic] = []
        context = {
            "site": self._site_context(site),
            "theme": self._theme_context(site, diagnostics),
            "t": self.theme.strings_for(site.metadata.language),
        }
        description = site.metadata.description

        def render(
            kind: str, route: Route | None, template: str = "", /, **page: object
        ) -> str:
            page.setdefault("description", description)
            page.setdefault("json_ld", None)
            for name in _PAGE_FIELDS:
                page.setdefault(name, None)
            template = template or self.theme.template_for(kind)
            return self.env.get_template(template).render(
                page=SimpleNamespace(kind=kind, route=route, **page), **context
            )

        routes = site.routes
        home = routes.route("home")
        first = site.archives[0]
        files = {
            home.output_path: render(
                "home",
                home,
                json_ld=self._home_json_ld(site, home),
                items=first.posts,
                pagination=_pagination(first),
            )
        }
        for archive in site.archives:
            files[archive.route.output_path] = render(
                "blog",
                archive.route,
                items=archive.posts,
                pagination=_pagination(archive),
            )
        posts: tuple[BlogPost, ...] = context["site"].posts
        for index, post in enumerate(posts):
            files[post.route.output_path] = render(
                "post",
                post.route,
                description=post.description,
                json_ld=self._blog_json_ld(site, post),
                item=post,
                **_neighbours(posts, index),
            )
        if ideas := routes.get("ideas"):
            files[ideas.output_path] = render(
                "ideas", ideas, items=site.ideas, pagination=_single()
            )
        for index, idea in enumerate(site.ideas):
            files[idea.route.output_path] = render(
                "idea",
                idea.route,
                description=idea.description,
                json_ld=self._idea_json_ld(idea),
                item=idea,
                **_neighbours(site.ideas, index),
            )
        if (about := site.about) is not None:
            files[about.route.output_path] = render(
                "about",
                about.route,
                description=about.description,
                json_ld=self._about_json_ld(site, about),
                item=about,
            )
        if projects := routes.get("projects"):
            files[projects.output_path] = render(
                "projects", projects, items=site.projects, pagination=_single()
            )
        if tags := routes.get("tags"):
            files[tags.output_path] = render(
                "tags", tags, items=site.tags, pagination=_single()
            )
        for tag in site.tags:
            files[tag.route.output_path] = render(
                "tag", tag.route, items=tag.posts, tag=tag, pagination=_single()
            )
        for extra in site.extra_pages:
            project = extra.project
            files[extra.route.output_path] = render(
                "page",
                extra.route,
                extra.template,
                description=(project.summary if project else "") or description,
                project=project,
            )
        if self.theme.has_template(NOT_FOUND_TEMPLATE):
            files[NOT_FOUND_TEMPLATE] = render("404", None, NOT_FOUND_TEMPLATE)

        files[site.feed.route.output_path] = render_atom_xml(
            site.feed, site.metadata, home.canonical_url
        )
        files[routes.route("sitemap").output_path] = self._sitemap(site)
        files[routes.route("robots").output_path] = (
            f"User-agent: *\nAllow: /\nSitemap: {routes.route('sitemap').canonical_url}\n"
        )
        files[routes.route("search").output_path] = json.dumps(
            build_search_index(site), ensure_ascii=False, separators=(",", ":")
        )
        return RenderedSite(files, tuple(diagnostics))

    @staticmethod
    def _site_context(site: SiteModel) -> SimpleNamespace:
        metadata = site.metadata
        routes = SimpleNamespace(
            **{name: site.routes.get(name) for name in _SITE_ROUTES}
        )
        return SimpleNamespace(
            title=metadata.title,
            author=metadata.author,
            description=metadata.description,
            language=metadata.language,
            url=routes.home.canonical_url,
            repo=metadata.repo,
            profile=metadata.profile,
            navigation=metadata.navigation,
            comments=metadata.comments,
            seo=metadata.seo,
            routes=routes,
            posts=tuple(sorted(site.blogs, key=blog_post_sort_key, reverse=True)),
            ideas=site.ideas,
            projects=site.projects,
            featured_projects=tuple(p for p in site.projects if p.featured),
            tags=site.tags,
            about=site.about,
        )

    def _theme_context(
        self, site: SiteModel, diagnostics: list[Diagnostic]
    ) -> SimpleNamespace:
        """Resolved options; ``posts`` options become the Blog posts they name."""
        values = dict(vars(self.options))
        by_number = {post.issue_number: post for post in site.blogs}
        for name, spec in self.theme.options.items():
            if spec.type != "posts":
                continue
            found = []
            for number in values[name]:
                if number in by_number:
                    found.append(by_number[number])
                else:
                    diagnostics.append(
                        Diagnostic(
                            "warning",
                            "THEME_OPTION_POST_MISSING",
                            f"theme.options.{name}: Issue #{number} is not a "
                            "published Blog post; it is left out",
                            issue_number=number,
                            field=f"theme.options.{name}",
                        )
                    )
            values[name] = tuple(found)
        return SimpleNamespace(**values)

    @staticmethod
    def _sitemap(site: SiteModel) -> str:
        urlset = ET.Element(
            "urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        )
        for route in site.routes.sitemap_routes():
            ET.SubElement(
                ET.SubElement(urlset, "url"), "loc"
            ).text = route.canonical_url
        return ET.tostring(urlset, encoding="unicode", xml_declaration=True)

    @staticmethod
    def _home_json_ld(site: SiteModel, home: Route) -> dict[str, Any]:
        metadata = site.metadata
        return {
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "Person", "name": metadata.author, "url": home.canonical_url},
                {
                    "@type": "WebSite",
                    "@id": home.canonical_url,
                    "name": metadata.title,
                    "url": home.canonical_url,
                    "description": metadata.description,
                },
            ],
        }

    @staticmethod
    def _about_json_ld(
        site: SiteModel, about: AboutPage | ProfileAbout
    ) -> dict[str, Any]:
        if isinstance(about, ProfileAbout):
            return {
                "@context": "https://schema.org",
                "@type": "AboutPage",
                "url": about.canonical_url,
                "description": about.description,
                "name": about.title,
            }
        return {
            "@context": "https://schema.org",
            "@type": "Person",
            "name": site.metadata.author,
            "url": about.canonical_url,
            "description": about.description,
        }

    @staticmethod
    def _blog_json_ld(site: SiteModel, post: BlogPost) -> dict[str, Any]:
        return {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": post.title,
            "description": post.description,
            "url": post.route.canonical_url,
            "datePublished": post.published_at.astimezone(UTC).isoformat(),
            "dateModified": post.updated_at.astimezone(UTC).isoformat(),
            "author": {"@type": "Person", "name": site.metadata.author},
        }

    @staticmethod
    def _idea_json_ld(idea: Idea) -> dict[str, str]:
        return {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": idea.title,
            "description": idea.description,
            "url": idea.canonical_url,
        }


def _pagination(archive: ArchivePage) -> SimpleNamespace:
    return SimpleNamespace(
        number=archive.page_number,
        total=archive.total_pages,
        prev=archive.prev_route,
        next=archive.next_route,
    )


def _single() -> SimpleNamespace:
    """A list shown on one page."""
    return SimpleNamespace(number=1, total=1, prev=None, next=None)


def _neighbours(items: Sequence[object], index: int) -> dict[str, object]:
    """The newer and older item, for a list sorted newest first."""
    return {
        "newer": items[index - 1] if index else None,
        "older": items[index + 1] if index + 1 < len(items) else None,
    }
