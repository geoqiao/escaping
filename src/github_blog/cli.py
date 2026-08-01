import os
import shutil
import sys
from pathlib import Path

import structlog
from github.Issue import Issue

from .config import GithubConfig, Settings
from .output_safety import (
    OutputContainmentError,
    validate_output_child_name,
    validate_output_containment,
)
from .services.github_service import GitHubService
from .services.render_service import RenderService
from .utils.slug import generate_slug_from_title

logger = structlog.get_logger()

# Home recent Blog count is fixed at 5 for v1 (not configurable).
HOME_POST_COUNT = 5


class BlogGenerator:
    def __init__(self, token: str, repo_name: str, settings: Settings) -> None:
        self.gh = GitHubService(token)
        self.repo_name: str = repo_name
        self.settings: Settings = settings
        self.render = RenderService(settings)

    def generate(self) -> None:
        logger.info("start_generation", repo=self.repo_name)
        try:
            repo = self.gh.get_repo(self.repo_name)
            issues = self.gh.get_user_issues(repo)

            # Generate a slug for each issue (based on title, stable and readable)
            issue_slugs = {}
            for issue in issues:
                slug = generate_slug_from_title(issue.number, issue.title)
                issue_slugs[str(issue.number)] = slug

            # Validate output containment before any filesystem mutation
            try:
                validate_output_containment(self.settings.paths.output, Path.cwd())
            except OutputContainmentError as e:
                logger.error("output_containment_failed", error=str(e))
                sys.exit(1)

            # Validate tag names before any filesystem mutation
            try:
                tags = self._collect_tags(issues)
            except OutputContainmentError as e:
                logger.error("tag_validation_failed", error=str(e))
                sys.exit(1)

            # Initialize directories and copy theme static assets
            self._init_dirs()
            self._copy_theme_assets()

            # Render posts
            for issue in issues:
                html_body = self.render.markdown_to_html(issue.body or "")
                content = self.render.render_post(
                    issue, issue_slugs[str(issue.number)], html_body
                )
                self._save_post(issue_slugs[str(issue.number)], content)

            # Render post index page
            self._generate_index(issues, tags, issue_slugs)

            # Render landing page (placed in output/ root)
            post_count = HOME_POST_COUNT
            home_content = self.render.render_home(issues[:post_count], issue_slugs)
            (Path(self.settings.paths.output) / "index.html").write_text(
                home_content, encoding="utf-8"
            )

            # Render tag pages
            self._generate_tag_pages(issues, tags, issue_slugs)

            # Generate RSS (placed in output/ root)
            rss_content = self.render.generate_rss(issues, issue_slugs)
            (Path(self.settings.paths.output) / self.settings.paths.rss).write_text(
                rss_content, encoding="utf-8"
            )

            # Generate Sitemap (placed in output/ root)
            sitemap_content = self.render.render_sitemap(issues, issue_slugs, tags)
            (Path(self.settings.paths.output) / "sitemap.xml").write_text(
                sitemap_content, encoding="utf-8"
            )

            # Generate Robots.txt (placed in output/ root)
            robots_content = self.render.render_robots()
            (Path(self.settings.paths.output) / "robots.txt").write_text(
                robots_content, encoding="utf-8"
            )

            # Render about page (placed in output/ root)
            about_content = self.render.render_about()
            (Path(self.settings.paths.output) / self.settings.paths.about).write_text(
                about_content, encoding="utf-8"
            )

            logger.info("generation_completed")
        except Exception:
            logger.exception("generation_failed")
            sys.exit(1)

    def _init_dirs(self) -> None:
        output = Path(self.settings.paths.output)
        if output.exists():
            shutil.rmtree(output)
        output.mkdir(parents=True)
        (output / self.settings.paths.blog).mkdir(parents=True)
        (output / self.settings.paths.blog / self.settings.paths.page).mkdir(
            parents=True
        )
        (output / self.settings.paths.tag).mkdir(parents=True)

    def _save_post(self, slug: str, content: str) -> None:
        path = (
            Path(self.settings.paths.output) / self.settings.paths.blog / f"{slug}.html"
        )
        path.write_text(content, encoding="utf-8")

    def _copy_theme_assets(self) -> None:
        """Copy theme static assets into output directory."""
        theme_src = Path(self.settings.paths.theme_path)
        if not theme_src.exists():
            raise FileNotFoundError(f"Theme directory not found: {theme_src}")

        static_src = theme_src / "static"
        static_dst = Path(self.settings.paths.theme_static_dst)
        if static_src.exists():
            shutil.copytree(static_src, static_dst, dirs_exist_ok=True)

        images_src = theme_src / "images"
        images_dst = Path(self.settings.paths.theme_images_dst)
        if images_src.exists():
            shutil.copytree(images_src, images_dst, dirs_exist_ok=True)

    def _collect_tags(self, issues: list[Issue]) -> list[str]:
        tagset = set()
        for issue in issues:
            if issue.labels:
                for label in issue.labels:
                    validate_output_child_name(label.name, "tag")
                    tagset.add(label.name)
        return sorted(tagset)

    def _generate_index(
        self, issues: list[Issue], tags: list[str], issue_slugs: dict[str, str]
    ) -> None:
        page_size = self.settings.paths.page_size
        pages = [issues[i : i + page_size] for i in range(0, len(issues), page_size)]
        total_pages = max(1, len(pages))

        page_dir = (
            Path(self.settings.paths.output)
            / self.settings.paths.blog
            / self.settings.paths.page
        )
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
                (
                    Path(self.settings.paths.output)
                    / self.settings.paths.blog
                    / "index.html"
                ).write_text(content, encoding="utf-8")

            (
                Path(self.settings.paths.output)
                / self.settings.paths.blog
                / self.settings.paths.page
                / f"{i}.html"
            ).write_text(content, encoding="utf-8")

    def _generate_tag_pages(
        self, issues: list[Issue], tags: list[str], issue_slugs: dict[str, str]
    ) -> None:
        tag_index = {}
        for issue in issues:
            if issue.labels:
                for label in issue.labels:
                    name = label.name
                    if name not in tag_index:
                        tag_index[name] = []
                    tag_index[name].append(issue)

        # Generate tag list page (tag/index.html)
        tag_counts = {tag: len(tag_index.get(tag, [])) for tag in tags}
        tags_content = self.render.render_tags_page(tags, tag_counts)
        (
            Path(self.settings.paths.output) / self.settings.paths.tag / "index.html"
        ).write_text(tags_content, encoding="utf-8")

        for tag in tags:
            tag_issues = tag_index.get(tag, [])
            if tag_issues:
                content = self.render.render_tag_page(
                    tag, tag_issues, tags, issue_slugs
                )
                (
                    Path(self.settings.paths.output)
                    / self.settings.paths.tag
                    / f"{tag}.html"
                ).write_text(content, encoding="utf-8")


def run_cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="GitHub Blog Generator")
    parser.add_argument(
        "--repo",
        help="GitHub Repository (e.g., user/repo). Overrides config.yaml if provided.",
    )
    args = parser.parse_args()

    # Load settings from config.yaml
    settings = Settings.load_from_yaml(Path("config.yaml"))

    # Read token from the environment variable specified in config
    token = os.environ.get(settings.security.token_env)
    if not token:
        logger.error("missing_token", env_var=settings.security.token_env)
        sys.exit(1)

    # If --repo override is provided, validate it with the same strict
    # GithubConfig rules and update settings so the override propagates
    # everywhere: fetch source, template/common context, and Utterances
    # fallback.  allowed_authors from config is preserved.
    if args.repo:
        settings.github = GithubConfig(
            repo=args.repo,
            allowed_authors=settings.github.allowed_authors,
        )

    repo_name = settings.github.repo

    generator = BlogGenerator(token, repo_name, settings)
    generator.generate()
