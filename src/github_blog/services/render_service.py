from __future__ import annotations

import re
import shutil
import xml.etree.ElementTree as ET
from datetime import timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from marko import Markdown
from marko.ext.gfm import GFM
from marko.html_renderer import HTMLRenderer
from marko.inline import Image

from ..atom_feed import render_atom_xml
from ..config import Settings, ThemeLockConfig
from ..models.blog_archive import ArchivePage
from ..models.blog_post import BlogPost
from ..models.content import AboutPage, Idea
from ..models.home_page import HomePage
from ..models.projects import ProjectsPage
from ..models.site import SiteModel
from ..models.tag_taxonomy import TagArchive, TagsIndex
from ..routes import RouteRegistry
from ..theme import ResolvedTheme, ThemeResolver
from ..utils.html_sanitizer import sanitize_html


class LazyImageRenderer(HTMLRenderer):
    """Marko renderer that keeps authored images lazy without trusting HTML."""

    def render_image(self, element: Image) -> str:
        result = super().render_image(element)
        return re.sub(r"<img\b", '<img loading="lazy"', result, count=1)


class RenderService:
    """Render only immutable internal models and registered route values."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.theme_source: ResolvedTheme | None = None
        self._active_routes: RouteRegistry | None = None
        configured_lock = getattr(settings, "theme_lock", None)
        if isinstance(configured_lock, ThemeLockConfig):
            override_dir = Path("templates") / "overrides" / settings.paths.theme
            if not override_dir.is_dir():
                override_dir = None
            self.theme_source = ThemeResolver(
                Path.cwd(),
                configured_lock,
                theme_name=settings.paths.theme,
                override_dir=override_dir,
            ).resolve()
            self.env = self.theme_source.environment()
        else:
            self.env = Environment(
                loader=FileSystemLoader(str(settings.paths.theme_path)),
                autoescape=True,
                undefined=StrictUndefined,
            )
        self.markdown = Markdown(extensions=[GFM, "pangu"], renderer=LazyImageRenderer)

    def _get_common_context(self) -> dict[str, Any]:
        routes = self._active_routes or RouteRegistry(str(self.settings.site.url))
        home_route = routes.home()
        atom_route = routes.atom()
        theme_path = self.settings.paths.theme_url_path
        return {
            "blog_title": self.settings.site.title,
            "github_name": self.settings.github.username,
            "github_repo": self.settings.github.repo,
            "blog_url": str(self.settings.site.url),
            "site_origin": str(self.settings.site.url).rstrip("/"),
            "home_url": routes.url(home_route),
            "atom_url": routes.url(atom_route),
            "theme_favicon_url": (
                f"{routes.origin}{theme_path}/static/images/favicon.png"
            ),
            "author_name": self.settings.site.author,
            "meta_description": self.settings.site.description,
            "google_search_verification": self.settings.seo.google_search_console,
            "theme_path": theme_path,
            "language": self.settings.site.language,
            "skip_link_text": "Skip to main content",
            "navigation": self.settings.site.navigation,
            "navigation_items": self.settings.site.navigation.items,
            "about_avatar": self.settings.profile.avatar,
            "about_bio": self.settings.profile.bio,
            "about_links": self.settings.profile.links,
            "branding": self.settings.branding.model_dump(),
            "comments": {
                "provider": self.settings.comments.provider,
                "repo": self.settings.comments.repo or self.settings.github.repo,
                "theme": self.settings.comments.theme,
                "theme_mode": self.settings.comments.theme_mode,
            },
        }

    def markdown_to_html(self, markdown: str) -> str:
        """Render a Markdown fragment for diagnostics/tracers; sanitize output."""
        markdown = re.sub(
            r"\[(#[\w-]+)\]\(https://github\.com/[^/]+/[^/]+/issues/new[^\)]*\)",
            r"\1",
            markdown,
        )
        return sanitize_html(self.markdown.convert(markdown))

    def render_site(self, site: SiteModel) -> dict[str, str]:
        """Render every page and machine-readable artifact in one model pass."""
        if site.about is None:
            raise ValueError("strict SiteModel requires AboutPage")
        self._active_routes = site.routes
        artifacts: dict[str, str] = {
            self._route_output(
                site, site.home.route.canonical_path
            ): self.render_home_page(site.home),
            self._route_output(
                site, site.about.route.canonical_path
            ): self.render_about_page(site.about),
            self._route_output(
                site, site.projects.route.canonical_path
            ): self.render_projects(site.projects),
            self._route_output(
                site, site.tags.route.canonical_path
            ): self.render_tag_index(site.tags),
            site.routes.route("atom").output_path: render_atom_xml(site.feed),
            site.routes.route("sitemap").output_path: self.render_sitemap(site),
            site.routes.route("robots").output_path: self.render_robots(site),
        }
        for page in site.archives:
            artifacts[self._route_output(site, page.route.canonical_path)] = (
                self.render_blog_archive(page)
            )
        for post in site.blogs:
            artifacts[self._route_output(site, post.canonical_path)] = (
                self.render_blog_detail(post)
            )
        ideas_route = site.routes.route("ideas")
        artifacts[ideas_route.output_path] = self.render_ideas(
            site.ideas, ideas_route.canonical_url
        )
        for idea in site.ideas:
            artifacts[self._route_output(site, idea.canonical_path)] = self.render_idea(
                idea
            )
        for archive in site.tag_archives:
            artifacts[self._route_output(site, archive.route.canonical_path)] = (
                self.render_tag_archive(archive)
            )
        return artifacts

    @staticmethod
    def _route_output(site: SiteModel, canonical_path: str) -> str:
        route = site.routes.route_for_path(canonical_path)
        if route is None:
            raise ValueError(f"unregistered canonical route: {canonical_path}")
        return route.output_path

    def copy_theme_assets(self, output_dir: Path) -> None:
        destination = output_dir / "templates" / self.settings.paths.theme / "static"
        if self.theme_source is not None:
            self._copy_resolved_assets(destination, self.theme_source)
            return
        source = Path(self.settings.paths.theme_path) / "static"
        if not source.is_dir():
            raise FileNotFoundError(f"theme static assets not found: {source}")
        shutil.copytree(source, destination, dirs_exist_ok=True)

    def render_home_page(self, home: HomePage) -> str:
        context = self._get_common_context()
        home_routes = RouteRegistry(home.canonical_url)
        context.update(
            {
                "blog_title": home.site_title,
                "author_name": home.site_author,
                "github_name": home.site_author,
                "meta_description": home.site_description,
                "blog_url": home.canonical_url,
                "home_url": home.canonical_url,
                "atom_url": home_routes.url(home_routes.atom()),
                "page_canonical_url": home.canonical_url,
                "theme_favicon_url": (
                    f"{home.canonical_url.rstrip('/')}"
                    f"{self.settings.paths.theme_url_path}/static/images/favicon.png"
                ),
                "navigation_items": home.navigation,
                "structured_data": self._home_json_ld(home),
            }
        )
        return self.env.get_template("home.html").render(home_page=home, **context)

    def render_blog_detail(self, post: BlogPost) -> str:
        context = self._get_common_context()
        context["page_canonical_url"] = post.canonical_url
        context["structured_data"] = self._blog_json_ld(post)
        return self.env.get_template("post.html").render(post=post, **context)

    def render_blog_archive(self, page: ArchivePage) -> str:
        context = self._get_common_context()
        context["page_canonical_url"] = page.canonical_url
        return self.env.get_template("index.html").render(archive_page=page, **context)

    def render_tag_index(self, index: TagsIndex) -> str:
        context = self._get_common_context()
        context["page_canonical_url"] = index.canonical_url
        return self.env.get_template("tags.html").render(tags_index=index, **context)

    def render_tag_archive(self, archive: TagArchive) -> str:
        context = self._get_common_context()
        context["page_canonical_url"] = archive.canonical_url
        return self.env.get_template("tag.html").render(tag_archive=archive, **context)

    def render_ideas(
        self, ideas: tuple[Idea, ...], canonical_url: str | None = None
    ) -> str:
        context = self._get_common_context()
        ideas_url = canonical_url or f"{context['site_origin']}/ideas/"
        context["page_canonical_url"] = ideas_url
        context["ideas_canonical_url"] = ideas_url
        return self.env.get_template("ideas.html").render(ideas=ideas, **context)

    def render_idea(self, idea: Idea) -> str:
        context = self._get_common_context()
        context["page_canonical_url"] = idea.canonical_url
        context["structured_data"] = self._article_json_ld(
            idea.title, idea.description, idea.canonical_url
        )
        return self.env.get_template("idea.html").render(idea=idea, **context)

    def render_about_page(self, about: AboutPage) -> str:
        context = self._get_common_context()
        context["page_canonical_url"] = about.canonical_url
        context["structured_data"] = self._about_json_ld(about)
        return self.env.get_template("about.html").render(about_page=about, **context)

    def render_projects(self, projects: ProjectsPage) -> str:
        context = self._get_common_context()
        context["page_canonical_url"] = projects.canonical_url
        return self.env.get_template("projects.html").render(
            projects=projects, **context
        )

    def render_sitemap(self, site: SiteModel) -> str:
        urlset = ET.Element(
            "urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        )
        for path in site.routes.sitemap_routes():
            route = site.routes.route_for_path(path)
            if route is None:
                raise ValueError(f"sitemap contains unregistered route: {path}")
            ET.SubElement(urlset, "url").append(ET.Element("loc"))
            urlset[-1][0].text = site.routes.url(route)
        return ET.tostring(urlset, encoding="unicode", xml_declaration=True)

    def render_robots(self, site: SiteModel) -> str:
        return f"User-agent: *\nAllow: /\nSitemap: {site.routes.url(site.routes.route('sitemap'))}\n"

    @staticmethod
    def _copy_resolved_assets(destination: Path, source: ResolvedTheme) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        for directory in reversed(source.asset_dirs):
            static = directory / "static"
            if static.is_dir():
                shutil.copytree(static, destination, dirs_exist_ok=True)

    def _home_json_ld(self, home: HomePage) -> dict[str, Any]:
        return {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "Person",
                    "name": home.site_author,
                    "url": home.canonical_url,
                },
                {
                    "@type": "WebSite",
                    "name": home.site_title,
                    "url": home.canonical_url,
                    "description": home.site_description,
                },
            ],
        }

    def _about_json_ld(self, about: AboutPage) -> dict[str, Any]:
        return {
            "@context": "https://schema.org",
            "@type": "Person",
            "name": self.settings.site.author,
            "url": about.canonical_url,
            "description": about.description,
        }

    def _blog_json_ld(self, post: BlogPost) -> dict[str, Any]:
        return {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": post.title,
            "description": post.description,
            "url": post.canonical_url,
            "datePublished": post.published_at.astimezone(timezone.utc).isoformat(),
            "dateModified": post.updated_at.astimezone(timezone.utc).isoformat(),
            "author": {"@type": "Person", "name": self.settings.site.author},
        }

    @staticmethod
    def _article_json_ld(
        title: str, description: str, canonical_url: str
    ) -> dict[str, str]:
        return {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": title,
            "description": description,
            "url": canonical_url,
        }
