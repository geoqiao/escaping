from datetime import datetime
from typing import Any

from feedgen.feed import FeedGenerator
from github.Issue import Issue
from jinja2 import Environment, FileSystemLoader
from lxml.etree import CDATA  # type: ignore
from marko import Markdown
from marko.ext.gfm import GFM

from ..config import settings


class RenderService:
    def __init__(self):
        self.env = Environment(loader=FileSystemLoader(str(settings.theme.path)))
        self.markdown = Markdown(extensions=[GFM, "pangu"])

    def markdown_to_html(self, md_str: str) -> str:
        return self.markdown.convert(md_str)

    def render_post(self, issue: Issue, slug: str, html_body: str) -> str:
        template = self.env.get_template("post.html")
        return template.render(
            issue=issue,
            slug=slug,
            html_body=html_body,
            blog_title=settings.blog.title,
            github_name=settings.github.name,
            github_repo=settings.github.repo,
            author_name=settings.blog.author.name,
            author_email=settings.blog.author.email,
            blog_url=str(settings.blog.url),
            rss_atom_path=settings.blog.rss_atom_path,
            meta_description=settings.blog.description,
            google_search_verification=settings.google_search_console.content,
        )

    def render_index(
        self,
        issues: list[Issue],
        tags: list[str],
        pagination: dict[str, Any],
        issue_slugs: dict[int, str],
    ) -> str:
        template = self.env.get_template("index.html")
        return template.render(
            issues=issues,
            issue_slugs=issue_slugs,
            tags=tags,
            pagination=pagination,
            blog_title=settings.blog.title,
            github_name=settings.github.name,
            github_repo=settings.github.repo,
            blog_url=str(settings.blog.url),
            rss_atom_path=settings.blog.rss_atom_path,
            author_name=settings.blog.author.name,
            meta_description=settings.blog.description,
            google_search_verification=settings.google_search_console.content,
        )

    def render_home(self, issues: list[Issue], issue_slugs: dict[int, str]) -> str:
        template = self.env.get_template("home.html")
        return template.render(
            issues=issues,
            issue_slugs=issue_slugs,
            blog_title=settings.blog.title,
            github_name=settings.github.name,
            github_repo=settings.github.repo,
            blog_url=str(settings.blog.url),
            rss_atom_path=settings.blog.rss_atom_path,
            author_name=settings.blog.author.name,
            meta_description=settings.blog.description,
            google_search_verification=settings.google_search_console.content,
        )

    def render_tag_page(
        self,
        tag: str,
        issues: list[Issue],
        tags: list[str],
        issue_slugs: dict[int, str],
    ) -> str:
        template = self.env.get_template("tag.html")
        return template.render(
            tag_name=tag,
            issues=issues,
            issue_slugs=issue_slugs,
            tags=tags,
            blog_title=settings.blog.title,
            github_name=settings.github.name,
            github_repo=settings.github.repo,
            blog_url=str(settings.blog.url),
            rss_atom_path=settings.blog.rss_atom_path,
            author_name=settings.blog.author.name,
            meta_description=settings.blog.description,
            google_search_verification=settings.google_search_console.content,
        )

    def generate_rss(self, issues: list[Issue], issue_slugs: dict[int, str]) -> str:
        fg = FeedGenerator()
        fg.id(str(settings.blog.url))
        fg.title(settings.blog.title)
        fg.author(
            {"name": settings.blog.author.name, "email": settings.blog.author.email}
        )
        fg.link(href=str(settings.blog.url), rel="alternate")
        fg.description(settings.blog.description)

        for issue in issues:
            slug = issue_slugs[issue.number]
            fe = fg.add_entry()
            blog_dir_str = str(settings.blog.blog_dir).strip("/")
            url = f"{str(settings.blog.url).rstrip('/')}/contents/{blog_dir_str}/{slug}.html"
            fe.id(url)
            fe.title(issue.title)
            fe.link(href=url)
            fe.description(issue.body[:100] if issue.body else "")
            fe.published(issue.created_at)
            fe.updated(issue.updated_at)
            fe.content(CDATA(self.markdown_to_html(issue.body or "")), type="html")

        return fg.atom_str(pretty=True).decode("utf-8")

    def render_sitemap(
        self, issues: list[Issue], issue_slugs: dict[int, str], tags: list[str]
    ) -> str:
        # 显式加载 SEO 模板目录
        seo_env = Environment(loader=FileSystemLoader("templates/seo"))
        template = seo_env.get_template("sitemap.xml.j2")

        blog_items = []
        for issue in issues:
            blog_items.append(
                {
                    "slug": issue_slugs[issue.number],
                    "lastmod": issue.updated_at.strftime("%Y-%m-%d"),
                }
            )

        return template.render(
            base_url=str(settings.blog.url).rstrip("/"),
            blog_dir=str(settings.blog.blog_dir).strip("/"),
            blog_items=blog_items,
            tags=tags,
            now=datetime.now().strftime("%Y-%m-%d"),
        )

    def render_robots(self) -> str:
        seo_env = Environment(loader=FileSystemLoader("templates/seo"))
        template = seo_env.get_template("robots.txt.j2")
        return template.render(base_url=str(settings.blog.url).rstrip("/"))
