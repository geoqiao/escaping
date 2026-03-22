import sys
from pathlib import Path

import structlog
from github.Issue import Issue

from .config import settings
from .services.github_service import GitHubService
from .services.render_service import RenderService
from .utils.slug import generate_slug

logger = structlog.get_logger()


class BlogGenerator:
    def __init__(self, token: str, repo_name: str):
        self.gh = GitHubService(token)
        self.repo_name = repo_name
        self.render = RenderService()

    def generate(self):
        logger.info("start_generation", repo=self.repo_name)
        try:
            repo = self.gh.get_repo(self.repo_name)
            issues = self.gh.get_user_issues(repo)

            # 为每个 issue 生成 slug
            issue_slugs = {}
            for issue in issues:
                issue_tags = (
                    [label.name for label in issue.labels] if issue.labels else []
                )
                slug = generate_slug(issue.number, issue_tags)
                issue_slugs[issue.number] = slug
                issue_slugs[str(issue.number)] = slug

            # 目录初始化
            self._init_dirs()

            # 渲染文章
            for issue in issues:
                html_body = self.render.markdown_to_html(issue.body or "")
                content = self.render.render_post(
                    issue, issue_slugs[issue.number], html_body
                )
                self._save_post(issue_slugs[issue.number], content)

            # 渲染首页
            tags = self._collect_tags(issues)
            self._generate_index(issues, tags, issue_slugs)

            # 渲染主页 (landing page)
            home_content = self.render.render_home(issues[:3], issue_slugs)
            Path("index.html").write_text(home_content, encoding="utf-8")

            # 渲染标签页
            self._generate_tag_pages(issues, tags, issue_slugs)

            # 生成 RSS
            rss_content = self.render.generate_rss(issues, issue_slugs)
            (settings.blog.content_dir / settings.blog.rss_atom_path).write_text(
                rss_content, encoding="utf-8"
            )

            # 生成 Sitemap
            sitemap_content = self.render.render_sitemap(issues, issue_slugs, tags)
            Path("sitemap.xml").write_text(sitemap_content, encoding="utf-8")

            # 生成 Robots.txt
            robots_content = self.render.render_robots()
            Path("robots.txt").write_text(robots_content, encoding="utf-8")

            # 渲染 about 页面
            about_content = self.render.render_about()
            (settings.blog.content_dir / "about.html").write_text(about_content, encoding="utf-8")

            logger.info("generation_completed")
        except Exception as e:
            logger.error("generation_failed", error=str(e))
            sys.exit(2)

    def _init_dirs(self):
        content_dir = settings.blog.content_dir
        blog_dir = settings.blog.blog_dir
        if content_dir.exists():
            import shutil

            shutil.rmtree(content_dir)
        content_dir.mkdir(parents=True)
        (content_dir / blog_dir).mkdir(parents=True)

    def _save_post(self, slug: str, content: str):
        path = settings.blog.content_dir / settings.blog.blog_dir / f"{slug}.html"
        path.write_text(content, encoding="utf-8")

    def _collect_tags(self, issues: list[Issue]) -> list[str]:
        tagset = set()
        for issue in issues:
            if issue.labels:
                for label in issue.labels:
                    tagset.add(label.name)
        return sorted(tagset)

    def _generate_index(
        self, issues: list[Issue], tags: list[str], issue_slugs: dict[int, str]
    ):
        page_size = settings.blog.page_size
        pages = [issues[i : i + page_size] for i in range(0, len(issues), page_size)]
        total_pages = max(1, len(pages))

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
                (settings.blog.content_dir / "index.html").write_text(
                    content, encoding="utf-8"
                )

            page_dir = settings.blog.content_dir / "page"
            page_dir.mkdir(parents=True, exist_ok=True)
            (page_dir / f"{i}.html").write_text(content, encoding="utf-8")

    def _generate_tag_pages(
        self, issues: list[Issue], tags: list[str], issue_slugs: dict[int, str]
    ):
        tag_index = {}
        for issue in issues:
            if issue.labels:
                for label in issue.labels:
                    name = label.name
                    if name not in tag_index:
                        tag_index[name] = []
                    tag_index[name].append(issue)

        tag_dir = settings.blog.content_dir / "tag"
        tag_dir.mkdir(parents=True, exist_ok=True)
        for tag in tags:
            tag_issues = tag_index.get(tag, [])
            if tag_issues:
                content = self.render.render_tag_page(
                    tag, tag_issues, tags, issue_slugs
                )
                (tag_dir / f"{tag}.html").write_text(content, encoding="utf-8")


def run_cli():
    import argparse

    parser = argparse.ArgumentParser(description="GitHub Blog Generator")
    parser.add_argument("token", help="GitHub Personal Access Token")
    parser.add_argument("repo", help="GitHub Repository (e.g., user/repo)")
    args = parser.parse_args()

    generator = BlogGenerator(args.token, args.repo)
    generator.generate()
