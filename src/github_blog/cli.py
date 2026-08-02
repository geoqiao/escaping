from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import structlog
from github.Issue import Issue

from .build_result import BuildResult, Diagnostic
from .config import GithubConfig, Settings
from .output_safety import (
    OutputContainmentError,
    validate_output_child_name,
)
from .output_staging import (
    ArtifactValidator,
    BasicArtifactValidator,
    OutputStagingError,
    OutputStagingService,
)
from .services.github_service import GitHubService
from .services.render_service import RenderService
from .utils.slug import generate_slug_from_title

logger = structlog.get_logger()


class BlogGenerator:
    def __init__(
        self,
        token: str,
        repo_name: str,
        settings: Settings,
        *,
        github_service: GitHubService | None = None,
        render_service: RenderService | None = None,
        artifact_validator: ArtifactValidator | None = None,
        output_staging: OutputStagingService | None = None,
    ) -> None:
        self.gh = github_service if github_service is not None else GitHubService(token)
        self.repo_name: str = repo_name
        self.settings: Settings = settings
        self.render = (
            render_service if render_service is not None else RenderService(settings)
        )
        self.artifact_validator: ArtifactValidator = (
            artifact_validator
            if artifact_validator is not None
            else BasicArtifactValidator(settings)
        )
        self._output_staging = output_staging
        self._build_dir: Path = Path(self.settings.paths.output)

    def generate(self) -> BuildResult:
        logger.info("start_generation", repo=self.repo_name)
        diagnostics: list[Diagnostic] = []

        # --- Fetch issues ----------------------------------------------------
        try:
            repo = self.gh.get_repo(self.repo_name)
            issues = self.gh.get_user_issues(repo)
        except Exception:
            logger.exception("fetch_failed")
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="FETCH_FAILED",
                    message="Failed to fetch issues from GitHub",
                )
            )
            return BuildResult(success=False, diagnostics=tuple(diagnostics))

        # --- Prepare slugs (before any filesystem mutation) -------------
        try:
            issue_slugs: dict[str, str] = {}
            for issue in issues:
                slug = generate_slug_from_title(issue.number, issue.title)
                issue_slugs[str(issue.number)] = slug
        except Exception:
            logger.exception("slug_preparation_failed")
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="SLUG_PREPARATION_FAILED",
                    message="Failed to prepare slugs for issues",
                )
            )
            return BuildResult(success=False, diagnostics=tuple(diagnostics))

        # --- Validate output containment (before any mutation) ---------------
        # OutputStagingService.__init__ calls validate_output_containment.
        try:
            staging = self._output_staging or OutputStagingService(
                self.settings.paths.output, Path.cwd()
            )
        except OutputContainmentError as e:
            logger.error("output_containment_failed", error=str(e))
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="OUTPUT_CONTAINMENT_FAILED",
                    message=str(e),
                )
            )
            return BuildResult(success=False, diagnostics=tuple(diagnostics))

        # --- Validate tag names (before any filesystem mutation) ------------
        try:
            tags = self._collect_tags(issues)
        except OutputContainmentError as e:
            logger.error("tag_validation_failed", error=str(e))
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TAG_VALIDATION_FAILED",
                    message=str(e),
                )
            )
            return BuildResult(success=False, diagnostics=tuple(diagnostics))

        # --- Create staging directory (first filesystem mutation) -----------
        staging_dir: Path | None = None

        def _cleanup_and_fail() -> BuildResult:
            """Clean up staging directory and return a failed BuildResult."""
            if staging_dir is not None:
                try:
                    cleanup_diags = staging.cleanup(staging_dir)
                    diagnostics.extend(cleanup_diags)
                except Exception:
                    logger.exception("cleanup_failed")
                    diagnostics.append(
                        Diagnostic(
                            severity="error",
                            code="CLEANUP_FAILED",
                            message=(
                                f"Failed to clean up staging directory: {staging_dir}"
                            ),
                        )
                    )
            return BuildResult(success=False, diagnostics=tuple(diagnostics))

        try:
            staging_dir = staging.create_staging_directory()
        except Exception:
            logger.exception("staging_creation_failed")
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="STAGING_CREATION_FAILED",
                    message="Failed to create staging directory",
                )
            )
            return _cleanup_and_fail()

        # --- Render/output setup (directories and assets) -------------------
        try:
            self._build_dir = staging_dir

            # Initialize directories and copy theme static assets
            self._init_dirs()
            self._copy_theme_assets()
        except Exception:
            logger.exception("build_setup_failed")
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="BUILD_SETUP_FAILED",
                    message="Failed to initialize output directories or copy theme assets",
                )
            )
            return _cleanup_and_fail()

        # --- Render phase ----------------------------------------------------
        try:
            # Render posts
            for issue in issues:
                try:
                    html_body = self.render.markdown_to_html(issue.body or "")
                except Exception:
                    logger.exception(
                        "markdown_convert_failed", issue_number=issue.number
                    )
                    diagnostics.append(
                        Diagnostic(
                            severity="error",
                            code="MARKDOWN_CONVERT_FAILED",
                            message=f"Failed to convert Markdown for issue #{issue.number}",
                            issue_number=issue.number,
                        )
                    )
                    return _cleanup_and_fail()

                try:
                    content = self.render.render_post(
                        issue, issue_slugs[str(issue.number)], html_body
                    )
                except Exception:
                    logger.exception("render_failed", issue_number=issue.number)
                    diagnostics.append(
                        Diagnostic(
                            severity="error",
                            code="RENDER_FAILED",
                            message=f"Failed to render issue #{issue.number}",
                            issue_number=issue.number,
                        )
                    )
                    return _cleanup_and_fail()
                self._save_post(issue_slugs[str(issue.number)], content)

            # Render post index page
            self._generate_index(issues, tags, issue_slugs)

            # Render landing page (placed in staging root)
            # Pass ALL issues; the adapter sorts by publication ordering
            # and limits to the fixed v1 count of 5.
            home_content = self.render.render_home(issues, issue_slugs)
            (self._build_dir / "index.html").write_text(home_content, encoding="utf-8")

            # Render tag pages
            self._generate_tag_pages(issues, tags, issue_slugs)

            # Generate RSS (placed in staging root)
            rss_content = self.render.generate_rss(issues, issue_slugs)
            (self._build_dir / self.settings.paths.rss).write_text(
                rss_content, encoding="utf-8"
            )

            # Generate Sitemap (placed in staging root)
            sitemap_content = self.render.render_sitemap(issues, issue_slugs, tags)
            (self._build_dir / "sitemap.xml").write_text(
                sitemap_content, encoding="utf-8"
            )

            # Generate Robots.txt (placed in staging root)
            robots_content = self.render.render_robots()
            (self._build_dir / "robots.txt").write_text(
                robots_content, encoding="utf-8"
            )

            # Render about page (placed in staging root)
            about_content = self.render.render_about()
            (self._build_dir / self.settings.paths.about).write_text(
                about_content, encoding="utf-8"
            )
        except Exception:
            logger.exception("render_failed")
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="RENDER_FAILED",
                    message="Failed to render site content",
                )
            )
            return _cleanup_and_fail()

        # --- Validate candidate artifacts --------------------------------
        try:
            validation_diagnostics = self.artifact_validator.validate(staging_dir)
        except Exception:
            logger.exception("artifact_validation_failed")
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="ARTIFACT_VALIDATION_FAILED",
                    message="Artifact validation raised an exception",
                )
            )
            return _cleanup_and_fail()

        diagnostics.extend(validation_diagnostics)
        has_errors = any(d.severity == "error" for d in validation_diagnostics)
        if has_errors:
            logger.error(
                "artifact_validation_failed",
                errors=len(
                    [d for d in validation_diagnostics if d.severity == "error"]
                ),
            )
            return _cleanup_and_fail()

        # --- Publish: atomically replace final output --------------------
        # Warnings from validation are preserved in *diagnostics* but do
        # not block publication.
        try:
            publish_warnings = staging.publish(staging_dir)
            diagnostics.extend(publish_warnings)
        except (OutputStagingError, OSError) as e:
            logger.error("publish_failed", error=str(e))
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="PUBLISH_FAILED",
                    message=str(e),
                )
            )
            return _cleanup_and_fail()

        logger.info("generation_completed")
        return BuildResult(success=True, diagnostics=tuple(diagnostics))

    def _init_dirs(self) -> None:
        output = self._build_dir
        # The staging directory is freshly created by OutputStagingService.
        # Do NOT rmtree + recreate it: that would change the inode and
        # break staging-registration tracking.  Just ensure subdirectories
        # exist.
        output.mkdir(parents=True, exist_ok=True)
        (output / self.settings.paths.blog).mkdir(parents=True)
        (output / self.settings.paths.blog / self.settings.paths.page).mkdir(
            parents=True
        )
        (output / self.settings.paths.tag).mkdir(parents=True)

    def _save_post(self, slug: str, content: str) -> None:
        path = self._build_dir / self.settings.paths.blog / f"{slug}.html"
        path.write_text(content, encoding="utf-8")

    def _copy_theme_assets(self) -> None:
        """Copy theme static assets into the build directory."""
        theme_src = Path(self.settings.paths.theme_path)
        if not theme_src.exists():
            raise FileNotFoundError(f"Theme directory not found: {theme_src}")

        static_src = theme_src / "static"
        static_dst = (
            self._build_dir / "templates" / self.settings.paths.theme / "static"
        )
        if static_src.exists():
            shutil.copytree(static_src, static_dst, dirs_exist_ok=True)

        images_src = theme_src / "images"
        images_dst = (
            self._build_dir / "templates" / self.settings.paths.theme / "images"
        )
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
        if not pages:
            pages = [[]]
        total_pages = len(pages)

        page_dir = self._build_dir / self.settings.paths.blog / self.settings.paths.page
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
                (self._build_dir / self.settings.paths.blog / "index.html").write_text(
                    content, encoding="utf-8"
                )

            (
                self._build_dir
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
        (self._build_dir / self.settings.paths.tag / "index.html").write_text(
            tags_content, encoding="utf-8"
        )

        for tag in tags:
            tag_issues = tag_index.get(tag, [])
            if tag_issues:
                content = self.render.render_tag_page(
                    tag, tag_issues, tags, issue_slugs
                )
                (self._build_dir / self.settings.paths.tag / f"{tag}.html").write_text(
                    content, encoding="utf-8"
                )


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
    result = generator.generate()
    for d in result.diagnostics:
        extra: dict[str, str | int] = {"code": d.code, "message": d.message}
        if d.issue_number is not None:
            extra["issue_number"] = d.issue_number
        if d.field is not None:
            extra["field"] = d.field
        if d.severity == "error":
            logger.error("build_diagnostic", **extra)
        elif d.severity == "warning":
            logger.warning("build_diagnostic", **extra)
    if not result.success:
        sys.exit(1)
