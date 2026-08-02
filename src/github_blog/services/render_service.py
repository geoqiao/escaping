import re
from datetime import datetime
from typing import Any

from feedgen.feed import FeedGenerator
from github.Issue import Issue
from jinja2 import Environment, FileSystemLoader
from lxml.etree import CDATA  # type: ignore
from marko import Markdown
from marko.ext.gfm import GFM
from marko.html_renderer import HTMLRenderer
from marko.inline import Image

from ..config import Settings
from ..models.blog_archive import ArchiveEntry, ArchivePage, ArchivePageRoute
from ..models.blog_post import BlogPost, BlogTag
from ..models.home_page import (
    HomeNavigationLink,
    HomePage,
    HomePostEntry,
    HomeProfile,
    HomeProfileLink,
    HomeRoute,
)
from ..utils.html_sanitizer import sanitize_html


class LazyImageRenderer(HTMLRenderer):
    """Marko HTML renderer that adds loading=\"lazy\" to all img tags."""

    def render_image(self, element: Image) -> str:
        result = super().render_image(element)
        # Inject loading="lazy" into the <img> tag using regex for robustness
        return re.sub(r"<img\b", '<img loading="lazy"', result, count=1)


class RenderService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.env = Environment(
            loader=FileSystemLoader(str(self.settings.paths.theme_path)),
            autoescape=True,
        )
        self.seo_env = Environment(
            loader=FileSystemLoader(str(self.settings.paths.seo_path)),
            autoescape=True,
        )
        self.markdown = Markdown(extensions=[GFM, "pangu"], renderer=LazyImageRenderer)

    def _get_common_context(self) -> dict[str, Any]:
        """Return context variables shared by all templates."""
        return {
            "blog_title": self.settings.site.title,
            "github_name": self.settings.github.username,
            "github_repo": self.settings.github.repo,
            "blog_url": str(self.settings.site.url),
            "rss_atom_path": self.settings.paths.rss,
            "author_name": self.settings.site.author,
            "meta_description": self.settings.site.description,
            "google_search_verification": self.settings.seo.google_search_console,
            "theme_path": self.settings.paths.theme_url_path,
            "language": self.settings.site.language,
            "skip_link_text": "Skip to main content",
            "navigation": self.settings.site.navigation,
            "navigation_items": self.settings.site.navigation.items,
            "about_avatar": self.settings.profile.avatar,
            "about_bio": self.settings.profile.bio,
            # expertise comes from About Issue Content in the new architecture;
            # empty list until content compilation is implemented.
            "about_expertise": [],
            "about_links": self.settings.profile.links,
            "branding": {
                "show_powered_by": self.settings.branding.show_powered_by,
                "powered_by_text": self.settings.branding.powered_by_text,
                "powered_by_url": self.settings.branding.powered_by_url,
                "show_intro": self.settings.branding.show_intro,
                "intro_text": self.settings.branding.intro_text,
                "intro_text2": self.settings.branding.intro_text2,
                "source_link_text": self.settings.branding.source_link_text,
                "source_link_url": self.settings.branding.source_link_url,
            },
            "comments": {
                "provider": self.settings.comments.provider,
                "repo": self.settings.comments.repo or self.settings.github.repo,
                "theme": self.settings.comments.theme,
                "theme_mode": self.settings.comments.theme_mode,
            },
        }

    def markdown_to_html(self, md_str: str) -> str:
        # Remove tag links that point to GitHub "new issue" pages so tags render as plain text
        md_str = re.sub(
            r"\[(#[\w-]+)\]\(https://github\.com/[^/]+/[^/]+/issues/new[^\)]*\)",
            r"\1",
            md_str,
        )
        return self.markdown.convert(md_str)

    def render_post(self, issue: Issue, slug: str, html_body: str) -> str:
        """Render a post detail page using the legacy path.

        Constructs a ``BlogPost`` from the legacy ``issue`` / ``slug`` /
        ``html_body`` parameters and delegates to :meth:`render_blog_detail`.
        This keeps the legacy ``BlogGenerator.generate()`` flow working while
        the post template consumes only ``BlogPost``.

        The ``html_body`` is sanitized to ensure any direct legacy Markdown
        conversion that reaches ``|safe`` in the template cannot inject
        dangerous HTML.

        Tags are wrapped in immutable ``BlogTag`` values whose ``path``
        matches the legacy writer's ``/{tag_dir}/{label.name}.html`` so
        detail tag hrefs point to the actual generated legacy tag files.
        The description falls back to ``settings.site.description`` because
        the legacy pipeline has no front-matter description.
        """
        labels = issue.labels or []
        tag_dir = self.settings.paths.tag
        tags = tuple(
            BlogTag(
                name=label.name,
                path=f"/{tag_dir}/{label.name}.html",
            )
            for label in labels
        )
        post = BlogPost(
            issue_number=issue.number,
            title=issue.title or "",
            slug=slug,
            description=self.settings.site.description,
            created_date=issue.created_at.strftime("%Y-%m-%d"),
            published_at=issue.created_at,
            updated_at=issue.updated_at,
            tags=tags,
            body_html=sanitize_html(html_body),
            canonical_path=f"/{self.settings.paths.blog}/{slug}.html",
        )
        return self.render_blog_detail(post)

    def render_blog_detail(self, post: BlogPost) -> str:
        """Render a Blog detail page from a compiled ``BlogPost``.

        This is the new clean seam: the template consumes only ``BlogPost``
        and shared context.  No PyGithub object, label interpretation, YAML
        parsing, or auxiliary slug map crosses into the template.
        """
        template = self.env.get_template("post.html")
        return template.render(
            post=post,
            **self._get_common_context(),
        )

    def render_blog_archive(self, page: ArchivePage) -> str:
        """Render an archive page from the internal page/entry model only."""
        template = self.env.get_template("index.html")
        return template.render(
            archive_page=page,
            **self._get_common_context(),
        )

    def render_index(
        self,
        issues: list[Issue],
        tags: list[str],
        pagination: dict[str, Any],
        issue_slugs: dict[str, str],
    ) -> str:
        """Adapt the legacy index inputs to the internal archive model.

        The default CLI continues to write its existing ``.html`` artifacts,
        while the archive template receives no PyGithub objects, label
        objects, pagination dictionary, or auxiliary slug map. Detail, tag,
        pagination, output, and canonical paths are all resolved here before
        delegating to :meth:`render_blog_archive`.
        """
        page_number = int(pagination["page"])
        total_pages = int(pagination["pages"])
        route = self._legacy_archive_route(page_number)
        page = ArchivePage(
            page_number=page_number,
            total_pages=total_pages,
            route=route,
            canonical_url=(
                f"{str(self.settings.site.url).rstrip('/')}{route.canonical_path}"
            ),
            prev_route=(
                self._legacy_pagination_route(int(pagination["prev_num"]))
                if pagination["has_prev"]
                else None
            ),
            next_route=(
                self._legacy_pagination_route(int(pagination["next_num"]))
                if pagination["has_next"]
                else None
            ),
            entries=tuple(
                ArchiveEntry(
                    title=issue.title or "",
                    created_date=issue.created_at.strftime("%Y-%m-%d"),
                    detail_path=(
                        f"/{self.settings.paths.blog}/"
                        f"{issue_slugs[str(issue.number)]}.html"
                    ),
                    tags=tuple(
                        BlogTag(
                            name=label.name,
                            path=f"/{self.settings.paths.tag}/{label.name}.html",
                        )
                        for label in (issue.labels or [])
                    ),
                )
                for issue in issues
            ),
        )
        return self.render_blog_archive(page)

    def _legacy_archive_route(self, page_number: int) -> ArchivePageRoute:
        """Return the canonical/output route for a legacy archive page."""
        blog_dir = self.settings.paths.blog
        if page_number == 1:
            return ArchivePageRoute(
                canonical_path=f"/{blog_dir}/",
                output_path=f"{blog_dir}/index.html",
            )
        return self._legacy_pagination_route(page_number)

    def _legacy_pagination_route(self, page_number: int) -> ArchivePageRoute:
        """Return a legacy ``.html`` pagination link/output route."""
        blog_dir = self.settings.paths.blog
        page_dir = self.settings.paths.page
        path = f"{blog_dir}/{page_dir}/{page_number}.html"
        return ArchivePageRoute(canonical_path=f"/{path}", output_path=path)

    def render_home(self, issues: list[Issue], issue_slugs: dict[str, str]) -> str:
        """Adapt the legacy Home inputs to the internal HomePage model.

        The default CLI continues to write its existing ``.html`` artifacts,
        while the home template receives no PyGithub objects, label objects,
        or auxiliary slug map.  The adapter receives *all* issues, sorts them
        by accepted publication ordering (``created_at`` desc with Issue
        number desc tie-breaker), and limits to the fixed v1 count of 5 before
        delegating to :meth:`render_home_page`.

        Legacy detail and tag hrefs match the existing ``.html`` writer so
        production pages are self-consistent.
        """
        from ..home_builder import HOME_POST_COUNT

        sorted_issues = sorted(
            issues,
            key=lambda issue: (issue.created_at, issue.number),
            reverse=True,
        )
        recent = sorted_issues[:HOME_POST_COUNT]

        blog_dir = self.settings.paths.blog
        tag_dir = self.settings.paths.tag
        base_url = str(self.settings.site.url).rstrip("/")

        home = HomePage(
            route=HomeRoute(canonical_path="/", output_path="index.html"),
            canonical_url=f"{base_url}/",
            site_title=self.settings.site.title,
            site_author=self.settings.site.author,
            site_description=self.settings.site.description,
            profile=HomeProfile(
                avatar=self.settings.profile.avatar,
                bio=self.settings.profile.bio,
                links=tuple(
                    HomeProfileLink(name=link.name, url=link.url)
                    for link in self.settings.profile.links
                ),
            ),
            navigation=tuple(
                HomeNavigationLink(name=item.name, url=item.url)
                for item in self.settings.site.navigation.items
            ),
            recent_posts=tuple(
                HomePostEntry(
                    title=issue.title or "",
                    created_date=issue.created_at.strftime("%Y-%m-%d"),
                    detail_path=(f"/{blog_dir}/{issue_slugs[str(issue.number)]}.html"),
                    tags=tuple(
                        BlogTag(
                            name=label.name,
                            path=f"/{tag_dir}/{label.name}.html",
                        )
                        for label in (issue.labels or [])
                    ),
                )
                for issue in recent
            ),
        )
        return self.render_home_page(home)

    def render_home_page(self, home: HomePage) -> str:
        """Render a Home page from the internal HomePage model only.

        This is the new clean seam: the template consumes only ``HomePage``
        and shared context.  No PyGithub object, Issue metadata, labels,
        branding, or auxiliary slug map crosses into the template.

        HomePage is the sole render source for Home identity/navigation:
        title, author, description, origin, theme-shell identity, and
        navigation are overridden with HomePage values so the base template
        header/footer/meta/nav reflect the HomePage, not Settings.
        """
        context = self._get_common_context()
        context["blog_title"] = home.site_title
        context["author_name"] = home.site_author
        context["github_name"] = home.site_author
        context["meta_description"] = home.site_description
        context["blog_url"] = home.canonical_url
        context["navigation_items"] = home.navigation
        template = self.env.get_template("home.html")
        return template.render(
            home_page=home,
            **context,
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
        fg.id(str(self.settings.site.url))
        fg.title(self.settings.site.title)
        fg.author(
            {
                "name": self.settings.site.author,
            }
        )
        fg.link(href=str(self.settings.site.url), rel="alternate")
        fg.description(self.settings.site.description)

        blog_dir_str = self.settings.paths.blog
        base_url = str(self.settings.site.url).rstrip("/")
        for issue in issues:
            slug = issue_slugs[str(issue.number)]
            fe = fg.add_entry()
            # New URL structure: /blog/{slug}.html
            url = f"{base_url}/{blog_dir_str}/{slug}.html"
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
            base_url=str(self.settings.site.url).rstrip("/"),
            blog_dir=self.settings.paths.blog,
            blog_items=blog_items,
            tags=tags,
            now=datetime.now().strftime("%Y-%m-%d"),
        )

    def render_robots(self) -> str:
        template = self.seo_env.get_template("robots.txt.j2")
        return template.render(base_url=str(self.settings.site.url).rstrip("/"))

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
