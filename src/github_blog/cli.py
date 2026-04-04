import shutil
import sys
from pathlib import Path

import structlog
from github.Issue import Issue

from .config import Settings, get_settings
from .services.github_service import GitHubService
from .services.render_service import RenderService
from .utils.slug import generate_slug_from_title

logger = structlog.get_logger()


class BlogGenerator:
    def __init__(self, token: str, repo_name: str):
        self.gh = GitHubService(token)
        self.repo_name = repo_name
        self.render = RenderService()
        self.settings: Settings = get_settings()

    def generate(self):
        logger.info("start_generation", repo=self.repo_name)
        try:
            repo = self.gh.get_repo(self.repo_name)
            issues = self.gh.get_user_issues(repo)

            # 为每个 issue 生成 slug (基于 title，稳定且可读)
            issue_slugs = {}
            for issue in issues:
                slug = generate_slug_from_title(issue.number, issue.title)
                issue_slugs[str(issue.number)] = slug

            # 目录初始化
            self._init_dirs()

            # 渲染文章
            for issue in issues:
                html_body = self.render.markdown_to_html(issue.body or "")
                content = self.render.render_post(
                    issue, issue_slugs[str(issue.number)], html_body
                )
                self._save_post(issue_slugs[str(issue.number)], content)

            # 渲染首页
            tags = self._collect_tags(issues)
            self._generate_index(issues, tags, issue_slugs)

            # 渲染主页 (landing page) (放到 output/ 根目录)
            post_count = self.settings.home.post_count
            home_content = self.render.render_home(issues[:post_count], issue_slugs)
            (self.settings.blog.content_dir / "index.html").write_text(
                home_content, encoding="utf-8"
            )

            # 渲染标签页
            self._generate_tag_pages(issues, tags, issue_slugs)

            # 生成 RSS (放到 output/ 根目录)
            rss_content = self.render.generate_rss(issues, issue_slugs)
            (
                self.settings.blog.content_dir / self.settings.blog.rss_atom_path
            ).write_text(rss_content, encoding="utf-8")

            # 生成 Sitemap (放到 output/ 根目录)
            sitemap_content = self.render.render_sitemap(issues, issue_slugs, tags)
            (self.settings.blog.content_dir / "sitemap.xml").write_text(
                sitemap_content, encoding="utf-8"
            )

            # 生成 Robots.txt (放到 output/ 根目录)
            robots_content = self.render.render_robots()
            (self.settings.blog.content_dir / "robots.txt").write_text(
                robots_content, encoding="utf-8"
            )

            # 渲染 about 页面 (放到 output/ 根目录)
            about_content = self.render.render_about()
            (self.settings.blog.content_dir / "about.html").write_text(
                about_content, encoding="utf-8"
            )

            logger.info("generation_completed")
        except Exception as e:
            logger.error("generation_failed", error=str(e))
            sys.exit(2)

    def _init_dirs(self):
        content_dir = self.settings.blog.content_dir
        blog_dir = self.settings.blog.blog_dir
        if content_dir.exists():
            shutil.rmtree(content_dir)
        content_dir.mkdir(parents=True)
        (content_dir / blog_dir).mkdir(parents=True)
        (content_dir / blog_dir / "page").mkdir(parents=True)
        (content_dir / "tag").mkdir(parents=True)

    def _save_post(self, slug: str, content: str):
        path = (
            self.settings.blog.content_dir
            / self.settings.blog.blog_dir
            / f"{slug}.html"
        )
        path.write_text(content, encoding="utf-8")

    def _collect_tags(self, issues: list[Issue]) -> list[str]:
        tagset = set()
        for issue in issues:
            if issue.labels:
                for label in issue.labels:
                    tagset.add(label.name)
        return sorted(tagset)

    def _generate_index(
        self, issues: list[Issue], tags: list[str], issue_slugs: dict[str, str]
    ):
        page_size = self.settings.blog.page_size
        pages = [issues[i : i + page_size] for i in range(0, len(issues), page_size)]
        total_pages = max(1, len(pages))

        page_dir = self.settings.blog.content_dir / "page"
        page_dir.mkdir(parents=True, exist_ok=True)

        for i, page_issues in enumerate(pages, start=1):
            pagination = {
                "page": i,
                "pages": total_pages,
                "has_prev": i > 1,
                "has_next": i < total_pages,
                "prev_num": i - 1,
                "next_num": i + 1,
            }
            content = self.render.render_index(
                page_issues, tags, pagination, issue_slugs
            )
            if i == 1:
                (self.settings.blog.content_dir / self.settings.blog.blog_dir / "index.html").write_text(
                    content, encoding="utf-8"
                )

            (self.settings.blog.content_dir / self.settings.blog.blog_dir / "page" / f"{i}.html").write_text(content, encoding="utf-8")

    def _generate_tag_pages(
        self, issues: list[Issue], tags: list[str], issue_slugs: dict[str, str]
    ):
        tag_index = {}
        for issue in issues:
            if issue.labels:
                for label in issue.labels:
                    name = label.name
                    if name not in tag_index:
                        tag_index[name] = []
                    tag_index[name].append(issue)

        tag_dir = self.settings.blog.content_dir / "tag"

        # 生成标签列表页面 (tag/index.html)
        tag_counts = {tag: len(tag_index.get(tag, [])) for tag in tags}
        tags_content = self.render.render_tags_page(tags, tag_counts)
        (self.settings.blog.content_dir / "tag" / "index.html").write_text(tags_content, encoding="utf-8")

        for tag in tags:
            tag_issues = tag_index.get(tag, [])
            if tag_issues:
                content = self.render.render_tag_page(
                    tag, tag_issues, tags, issue_slugs
                )
                (self.settings.blog.content_dir / "tag" / f"{tag}.html").write_text(content, encoding="utf-8")


def run_cli():
    import argparse

    parser = argparse.ArgumentParser(description="GitHub Blog Generator")
    parser.add_argument("token", help="GitHub Personal Access Token")
    parser.add_argument("repo", help="GitHub Repository (e.g., user/repo)")
    args = parser.parse_args()

    generator = BlogGenerator(args.token, args.repo)
    generator.generate()
