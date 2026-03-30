import re
from datetime import datetime
from pathlib import Path
from typing import Any

from feedgen.feed import FeedGenerator
from github.Issue import Issue
from jinja2 import Environment, FileSystemLoader
from lxml.etree import CDATA  # type: ignore
from marko import Markdown
from marko.ext.gfm import GFM
from marko.html_renderer import HTMLRenderer
from marko.inline import Image

from ..config import Settings, get_settings


class LazyImageRenderer(HTMLRenderer):
    """Marko HTML renderer that adds loading=\"lazy\" to all img tags."""

    def render_image(self, element: Image) -> str:
        result = super().render_image(element)
        # Inject loading="lazy" into the <img> tag using regex for robustness
        return re.sub(r"<img\b", '<img loading="lazy"', result, count=1)


class RenderService:
    def __init__(self):
        self.settings: Settings = get_settings()
        self.env = Environment(
            loader=FileSystemLoader(str(self.settings.theme.path)),
            autoescape=True,
        )
        # SEO templates are relative to theme path (e.g., templates/seo)
        seo_template_path = self.settings.theme.path.parent / "seo"
        self.seo_env = Environment(
            loader=FileSystemLoader(str(seo_template_path)),
            autoescape=True,
        )
        self.markdown = Markdown(extensions=[GFM, "pangu"], renderer=LazyImageRenderer)

    def _get_common_context(self) -> dict[str, Any]:
        """获取所有模板共用的上下文变量。"""
        return {
            "blog_title": self.settings.blog.title,
            "github_name": self.settings.github.name,
            "github_repo": self.settings.github.repo,
            "blog_url": str(self.settings.blog.url),
            "rss_atom_path": self.settings.blog.rss_atom_path,
            "author_name": self.settings.blog.author.name,
            "meta_description": self.settings.blog.description,
            "google_search_verification": self.settings.google_search_console.content,
            "theme_path": self.settings.theme.url_path,
        }

    def markdown_to_html(self, md_str: str) -> str:
        return self.markdown.convert(md_str)

    def render_post(self, issue: Issue, slug: str, html_body: str) -> str:
        template = self.env.get_template("post.html")
        return template.render(
            issue=issue,
            slug=slug,
            html_body=html_body,
            author_email=self.settings.blog.author.email,
            **self._get_common_context(),
        )

    def render_index(
        self,
        issues: list[Issue],
        tags: list[str],
        pagination: dict[str, Any],
        issue_slugs: dict[str, str],
    ) -> str:
        template = self.env.get_template("index.html")
        return template.render(
            issues=issues,
            issue_slugs=issue_slugs,
            tags=tags,
            pagination=pagination,
            **self._get_common_context(),
        )

    def render_home(self, issues: list[Issue], issue_slugs: dict[str, str]) -> str:
        template = self.env.get_template("home.html")
        return template.render(
            issues=issues,
            issue_slugs=issue_slugs,
            **self._get_common_context(),
        )

    def render_tag_page(
        self,
        tag: str,
        issues: list[Issue],
        tags: list[str],
        issue_slugs: dict[str, str],
    ) -> str:
        template = self.env.get_template("tag.html")
        return template.render(
            tag_name=tag,
            issues=issues,
            issue_slugs=issue_slugs,
            tags=tags,
            **self._get_common_context(),
        )

    def generate_rss(self, issues: list[Issue], issue_slugs: dict[str, str]) -> str:
        fg = FeedGenerator()
        fg.id(str(self.settings.blog.url))
        fg.title(self.settings.blog.title)
        fg.author(
            {
                "name": self.settings.blog.author.name,
                "email": self.settings.blog.author.email,
            }
        )
        fg.link(href=str(self.settings.blog.url), rel="alternate")
        fg.description(self.settings.blog.description)

        blog_dir_str = str(self.settings.blog.blog_dir).strip("/")
        base_url = str(self.settings.blog.url).rstrip("/")
        for issue in issues:
            slug = issue_slugs[str(issue.number)]
            fe = fg.add_entry()
            content_dir_str = str(self.settings.blog.content_dir).strip("./").strip("/")
            url = f"{base_url}/{content_dir_str}/{blog_dir_str}/{slug}.html"
            fe.id(url)
            fe.title(issue.title)
            fe.link(href=url)
            fe.description(issue.body[:100] if issue.body else "")
            fe.published(issue.created_at)
            fe.updated(issue.updated_at)
            fe.content(CDATA(self.markdown_to_html(issue.body or "")), type="html")

        return fg.atom_str(pretty=True).decode("utf-8")

    def render_sitemap(
        self, issues: list[Issue], issue_slugs: dict[str, str], tags: list[str]
    ) -> str:
        template = self.seo_env.get_template("sitemap.xml.j2")

        blog_items = [
            {
                "slug": issue_slugs[str(issue.number)],
                "lastmod": issue.updated_at.strftime("%Y-%m-%d"),
            }
            for issue in issues
        ]

        return template.render(
            base_url=str(self.settings.blog.url).rstrip("/"),
            blog_dir=str(self.settings.blog.blog_dir).strip("/"),
            blog_items=blog_items,
            tags=tags,
            now=datetime.now().strftime("%Y-%m-%d"),
        )

    def render_robots(self) -> str:
        template = self.seo_env.get_template("robots.txt.j2")
        return template.render(base_url=str(self.settings.blog.url).rstrip("/"))

    def render_about(self) -> str:
        template = self.env.get_template("about.html")
        return template.render(
            **self._get_common_context(),
        )

    def render_tags_page(
        self,
        tags: list[str],
        tag_counts: dict[str, int],
    ) -> str:
        template = self.env.get_template("tags.html")
        tag_items = [{"name": tag, "count": tag_counts.get(tag, 0)} for tag in tags]
        return template.render(
            tags=tags,
            tag_items=tag_items,
            **self._get_common_context(),
        )
