import os
import shutil
import sys
from pathlib import Path
from typing import Optional

import structlog
from github.Issue import Issue

from .config import Settings, get_settings, load_settings
from .services.github_service import GitHubService
from .services.render_service import RenderService
from .utils.slug import generate_slug_from_title

logger = structlog.get_logger()

# 从配置读取路径，不再硬编码
# CONTENT_DIR, BLOG_DIR, RSS_ATOM_PATH 等都从 self.settings.paths 获取

# Environment variable for GitHub token
TOKEN_ENV_VAR = "G_T"  # noqa: S105


class BlogGenerator:
    def __init__(self, token: str, repo_name: str):
        self.gh = GitHubService(token)
        self.repo_name: str = repo_name
        # Initialize settings before RenderService, which also calls get_settings()
        self.settings: Settings = get_settings()
        self.render = RenderService()

    def generate(self):
        logger.info("start_generation", repo=self.repo_name)
        try:
            repo = self.gh.get_repo(self.repo_name)
            issues = self.gh.get_user_issues(repo)

            # 为每个 issue 生成 slug (基于 title，稳定且可读)  # noqa: RUF003
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
            post_count = self.settings.paths.home_post_count
            home_content = self.render.render_home(issues[:post_count], issue_slugs)
            (Path(self.settings.paths.output) / "index.html").write_text(home_content, encoding="utf-8")

            # 渲染标签页
            self._generate_tag_pages(issues, tags, issue_slugs)

            # 生成 RSS (放到 output/ 根目录)
            rss_content = self.render.generate_rss(issues, issue_slugs)
            (Path(self.settings.paths.output) / self.settings.paths.rss).write_text(rss_content, encoding="utf-8")

            # 生成 Sitemap (放到 output/ 根目录)
            sitemap_content = self.render.render_sitemap(issues, issue_slugs, tags)
            (Path(self.settings.paths.output) / "sitemap.xml").write_text(sitemap_content, encoding="utf-8")

            # 生成 Robots.txt (放到 output/ 根目录)
            robots_content = self.render.render_robots()
            (Path(self.settings.paths.output) / "robots.txt").write_text(robots_content, encoding="utf-8")

            # 渲染 about 页面 (放到 output/ 根目录)
            about_content = self.render.render_about()
            (Path(self.settings.paths.output) / self.settings.paths.about).write_text(about_content, encoding="utf-8")

            logger.info("generation_completed")
        except Exception as e:
            logger.error("generation_failed", error=str(e))
            sys.exit(2)

    def _init_dirs(self):
        output = Path(self.settings.paths.output)
        if output.exists():
            shutil.rmtree(output)
        output.mkdir(parents=True)
        (output / self.settings.paths.blog).mkdir(parents=True)
        (output / self.settings.paths.blog / "page").mkdir(parents=True)
        (output / self.settings.paths.tag).mkdir(parents=True)

    def _save_post(self, slug: str, content: str):
        path = Path(self.settings.paths.output) / self.settings.paths.blog / f"{slug}.html"
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
        page_size = self.settings.paths.page_size
        pages = [issues[i : i + page_size] for i in range(0, len(issues), page_size)]
        total_pages = max(1, len(pages))

        page_dir = Path(self.settings.paths.output) / self.settings.paths.blog / "page"
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
                (Path(self.settings.paths.output) / self.settings.paths.blog / "index.html").write_text(
                    content, encoding="utf-8"
                )

            (Path(self.settings.paths.output) / self.settings.paths.blog / "page" / f"{i}.html").write_text(
                content, encoding="utf-8"
            )

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

        # 生成标签列表页面 (tag/index.html)
        tag_counts = {tag: len(tag_index.get(tag, [])) for tag in tags}
        tags_content = self.render.render_tags_page(tags, tag_counts)
        (Path(self.settings.paths.output) / self.settings.paths.tag / "index.html").write_text(tags_content, encoding="utf-8")

        for tag in tags:
            tag_issues = tag_index.get(tag, [])
            if tag_issues:
                content = self.render.render_tag_page(
                    tag, tag_issues, tags, issue_slugs
                )
                (Path(self.settings.paths.output) / self.settings.paths.tag / f"{tag}.html").write_text(
                    content, encoding="utf-8"
                )


def run_cli():
    import argparse

    parser = argparse.ArgumentParser(description="GitHub Blog Generator")
    parser.add_argument(
        "--repo",
        help="GitHub Repository (e.g., user/repo). Overrides config.yaml if provided.",
    )
    args = parser.parse_args()

    # Read token from G_T environment variable
    token = os.environ.get(TOKEN_ENV_VAR)
    if not token:
        logger.error("missing_token", env_var=TOKEN_ENV_VAR)
        sys.exit(1)

    # Load settings from config.yaml
    settings = load_settings()

    # Use CLI repo if provided, otherwise use config repo
    repo_name = args.repo if args.repo else settings.github.repo

    generator = BlogGenerator(token, repo_name)
    generator.generate()
