from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC
from pathlib import Path
from typing import Any

from jinja2 import Environment

from ..atom_feed import render_atom_xml
from ..models.blog_post import BlogPost
from ..models.content import AboutPage, Idea
from ..models.home_page import HomePage
from ..models.site import SiteMetadata, SiteModel
from ..theme import LoadedTheme


class RenderService:
    """Render one immutable SiteModel with one injected loaded Theme."""

    def __init__(self, theme: LoadedTheme) -> None:
        self.theme = theme
        self.env: Environment = theme.environment()

    def copy_theme_assets(self, output_dir: Path) -> None:
        self.theme.copy_assets(output_dir)

    def render_site(self, site: SiteModel) -> dict[str, str]:
        """Render every page and machine-readable artifact in one model pass."""
        if site.about is None:
            raise ValueError("strict SiteModel requires AboutPage")
        if self.theme.name != site.metadata.theme.name:
            raise ValueError(
                f"loaded Theme {self.theme.name!r} does not match SiteModel Theme "
                f"{site.metadata.theme.name!r}"
            )

        artifacts: dict[str, str] = {
            site.home.route.output_path: self._render_home(site, site.home),
            site.about.route.output_path: self._render_about(site, site.about),
            site.projects.route.output_path: self._render_projects(site),
            site.tags.route.output_path: self._render_tag_index(site),
            site.feed.route.output_path: render_atom_xml(
                site.feed, site.metadata, site.home.route.canonical_url
            ),
            site.routes.route("sitemap").output_path: self._render_sitemap(site),
            site.routes.route("robots").output_path: self._render_robots(site),
            site.ideas_page.route.output_path: self._render_ideas(site),
        }
        for page in site.archives:
            artifacts[page.route.output_path] = self.env.get_template(
                "index.html"
            ).render(
                archive_page=page,
                page_canonical_url=page.route.canonical_url,
                **self._common_context(site),
            )
        for post in site.blogs:
            artifacts[post.route.output_path] = self._render_blog(site, post)
        for idea in site.ideas:
            artifacts[idea.route.output_path] = self._render_idea(site, idea)
        for archive in site.tag_archives:
            artifacts[archive.route.output_path] = self.env.get_template(
                "tag.html"
            ).render(
                tag_archive=archive,
                page_canonical_url=archive.route.canonical_url,
                **self._common_context(site),
            )
        return artifacts

    def _common_context(self, site: SiteModel) -> dict[str, Any]:
        metadata = site.metadata
        home = site.routes.route("home")
        atom = site.routes.route("atom")
        return {
            "blog_title": metadata.title,
            "github_name": metadata.github_name,
            "github_repo": metadata.github_repo,
            "blog_url": home.canonical_url,
            "site_origin": site.routes.origin,
            "home_url": home.canonical_url,
            "home_path": home.canonical_path,
            "atom_url": atom.canonical_url,
            "theme_favicon_url": metadata.theme.favicon_url,
            "author_name": metadata.author,
            "meta_description": metadata.description,
            "google_search_verification": metadata.google_search_verification,
            "theme_path": metadata.theme.asset_path,
            "language": metadata.language,
            "skip_link_text": "Skip to main content",
            "navigation": metadata.navigation,
            "navigation_items": metadata.navigation,
            "about_avatar": metadata.profile.avatar,
            "about_bio": metadata.profile.bio,
            "about_links": metadata.profile.links,
            "branding": metadata.branding,
            "comments": metadata.comments,
            "metadata": metadata,
        }

    def _render_home(self, site: SiteModel, home: HomePage) -> str:
        context = self._common_context(site)
        context.update(
            {
                "page_canonical_url": home.route.canonical_url,
                "structured_data": self._home_json_ld(site.metadata, home),
                "top_projects": site.projects.top_by_stars(),
                "projects_path": site.projects.route.canonical_path,
            }
        )
        return self.env.get_template("home.html").render(home_page=home, **context)

    def _render_blog(self, site: SiteModel, post: BlogPost) -> str:
        context = self._common_context(site)
        context["page_canonical_url"] = post.route.canonical_url
        context["structured_data"] = self._blog_json_ld(site.metadata, post)
        return self.env.get_template("post.html").render(post=post, **context)

    def _render_tag_index(self, site: SiteModel) -> str:
        context = self._common_context(site)
        context["page_canonical_url"] = site.tags.route.canonical_url
        return self.env.get_template("tags.html").render(
            tags_index=site.tags, **context
        )

    def _render_ideas(self, site: SiteModel) -> str:
        context = self._common_context(site)
        canonical_url = site.ideas_page.route.canonical_url
        context["page_canonical_url"] = canonical_url
        context["ideas_canonical_url"] = canonical_url
        return self.env.get_template("ideas.html").render(
            ideas=site.ideas_page.ideas, **context
        )

    def _render_idea(self, site: SiteModel, idea: Idea) -> str:
        context = self._common_context(site)
        context["page_canonical_url"] = idea.route.canonical_url
        context["structured_data"] = self._article_json_ld(
            idea.title, idea.description, idea.route.canonical_url
        )
        return self.env.get_template("idea.html").render(idea=idea, **context)

    def _render_about(self, site: SiteModel, about: AboutPage) -> str:
        context = self._common_context(site)
        context["page_canonical_url"] = about.route.canonical_url
        context["structured_data"] = self._about_json_ld(site.metadata, about)
        return self.env.get_template("about.html").render(about_page=about, **context)

    def _render_projects(self, site: SiteModel) -> str:
        context = self._common_context(site)
        context["page_canonical_url"] = site.projects.route.canonical_url
        return self.env.get_template("projects.html").render(
            projects=site.projects, **context
        )

    @staticmethod
    def _render_sitemap(site: SiteModel) -> str:
        urlset = ET.Element(
            "urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        )
        for path in site.routes.sitemap_routes():
            route = site.routes.route_for_path(path)
            if route is None:
                raise ValueError(f"sitemap contains unregistered route: {path}")
            ET.SubElement(urlset, "url").append(ET.Element("loc"))
            urlset[-1][0].text = route.canonical_url
        return ET.tostring(urlset, encoding="unicode", xml_declaration=True)

    @staticmethod
    def _render_robots(site: SiteModel) -> str:
        sitemap = site.routes.route("sitemap").canonical_url
        return f"User-agent: *\nAllow: /\nSitemap: {sitemap}\n"

    @staticmethod
    def _home_json_ld(metadata: SiteMetadata, home: HomePage) -> dict[str, Any]:
        return {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "Person",
                    "name": metadata.author,
                    "url": home.route.canonical_url,
                },
                {
                    "@type": "WebSite",
                    "name": metadata.title,
                    "url": home.route.canonical_url,
                    "description": metadata.description,
                },
            ],
        }

    @staticmethod
    def _about_json_ld(metadata: SiteMetadata, about: AboutPage) -> dict[str, Any]:
        return {
            "@context": "https://schema.org",
            "@type": "Person",
            "name": metadata.author,
            "url": about.route.canonical_url,
            "description": about.description,
        }

    @staticmethod
    def _blog_json_ld(metadata: SiteMetadata, post: BlogPost) -> dict[str, Any]:
        return {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": post.title,
            "description": post.description,
            "url": post.route.canonical_url,
            "datePublished": post.published_at.astimezone(UTC).isoformat(),
            "dateModified": post.updated_at.astimezone(UTC).isoformat(),
            "author": {"@type": "Person", "name": metadata.author},
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
