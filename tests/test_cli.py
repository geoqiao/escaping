import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from github_blog.cli import BlogGenerator, run_cli


def _make_mock_issue(number, title, body="body", labels=None):
    issue = MagicMock()
    issue.number = number
    issue.title = title
    issue.body = body
    label_mocks = []
    if labels:
        for label in labels:
            m = MagicMock()
            m.name = label
            label_mocks.append(m)
    issue.labels = label_mocks
    # Use different timestamps to ensure stable sorting (newest first)
    issue.created_at = datetime(2024, 1, number, tzinfo=timezone.utc)
    issue.updated_at = datetime(2024, 1, number, tzinfo=timezone.utc)
    return issue


@patch("github_blog.cli.GitHubService")
def test_blog_generator_integration(mock_gh_service_class, tmp_path):
    # Get absolute path to the project root to find real templates
    project_root = Path(__file__).parent.parent.absolute()
    # Use Escape1 theme (the current default) for integration test
    real_template_path = project_root / "templates" / "Escape1"
    real_seo_path = project_root / "templates" / "seo"

    # Setup mock settings
    mock_settings = MagicMock()
    mock_settings.paths.page_size = 2
    mock_settings.paths.home_post_count = 10
    mock_settings.paths.output = "output"
    mock_settings.paths.blog = "blog"
    mock_settings.paths.tag = "tag"
    mock_settings.paths.about = "about.html"
    mock_settings.paths.rss = "atom.xml"
    mock_settings.blog.url = "https://example.com"
    mock_settings.blog.title = "Test Blog"
    mock_settings.blog.description = "Test Description"
    mock_settings.blog.author = "Author"
    mock_settings.github.username = "user"
    mock_settings.github.repo = "user/repo"
    # Use the absolute path to real templates
    mock_settings.paths.theme = "Escape1"
    mock_settings.paths.theme_path = str(real_template_path)
    mock_settings.paths.theme_url_path = "/templates/Escape1"
    mock_settings.paths.seo_path = str(real_seo_path)
    mock_settings.seo.google_search_console = ""
    mock_settings.about.avatar = ""
    mock_settings.about.bio = "Test bio"
    mock_settings.about.expertise = ["Skill 1", "Skill 2"]
    mock_settings.about.links = []
    mock_settings.navigation.items = []
    mock_settings.branding.show_powered_by = True
    mock_settings.branding.powered_by_text = "Powered by"
    mock_settings.branding.powered_by_url = "https://github.com/geoqiao/github-blog"
    mock_settings.branding.show_intro = False
    mock_settings.branding.intro_text = ""
    mock_settings.branding.intro_text2 = "Generated with Python + Jinja2, deployed via GitHub Actions."
    mock_settings.branding.source_link_text = "View Source"
    mock_settings.branding.source_link_url = ""
    mock_settings.comments.provider = "utterances"
    mock_settings.comments.repo = ""
    mock_settings.comments.theme = "github-light"
    mock_settings.comments.theme_mode = "auto"

    # Setup mock GitHub service
    mock_gh_service = mock_gh_service_class.return_value
    mock_repo = MagicMock()
    mock_gh_service.get_repo.return_value = mock_repo

    issues = [
        _make_mock_issue(1, "Post One", labels=["python"]),
        _make_mock_issue(2, "Post Two", labels=["python", "web"]),
    ]
    mock_gh_service.get_user_issues.return_value = issues

    # Create a temporary output directory to avoid polluting project root
    output_dir = tmp_path / "output"

    # Initialize and generate
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        # We need to mock RenderService because its __init__ hardcodes "templates/seo"
        # and it's called during BlogGenerator.__init__
        with patch(
            "github_blog.services.render_service.FileSystemLoader"
        ) as mock_loader:
            from jinja2 import FileSystemLoader

            def side_effect(path):
                # Ensure we handle both string and Path objects
                path_str = str(path)
                if "templates/seo" in path_str:
                    return FileSystemLoader(str(real_seo_path))
                if "templates/Escape1" in path_str or "Escape1" in path_str:
                    return FileSystemLoader(str(real_template_path))
                return FileSystemLoader(path)

            mock_loader.side_effect = side_effect

            # Re-initialize to apply the mock during RenderService.__init__
            generator = BlogGenerator("fake-token", "user/repo", mock_settings)
            generator.generate()

        # Verify files were created in tmp_path/output
        # Note: Slugs are now generated from title (not tags) for stability
        blog_dir = output_dir / "blog"
        assert (blog_dir / "1-post-one.html").exists()
        assert (blog_dir / "2-post-two.html").exists()
        assert (output_dir / "index.html").exists()
        assert (output_dir / "tag" / "python.html").exists()
        assert (output_dir / "tag" / "web.html").exists()
        assert (output_dir / "atom.xml").exists()

        # Verify output root files
        assert (output_dir / "sitemap.xml").exists()
        assert (output_dir / "robots.txt").exists()

        # Verify content of index.html for correct slugs (now title-based, new URL structure)
        index_content = (output_dir / "index.html").read_text()
        assert "/blog/1-post-one.html" in index_content
        assert "/blog/2-post-two.html" in index_content

        # Verify theme static assets were copied into output
        theme_static_dir = output_dir / "templates" / "Escape1" / "static"
        assert theme_static_dir.exists(), "Theme static directory should be copied to output"
        assert (theme_static_dir / "css" / "style.css").exists(), "Theme CSS should be present"
    finally:
        os.chdir(old_cwd)
        # Cleanup: remove the output directory if it exists in project root
        project_output = project_root / "output"
        if project_output.exists():
            shutil.rmtree(project_output)


class TestNewCLI:
    """Tests for the new CLI behavior (token from G_T env, repo from config or --repo flag)."""

    def test_cli_requires_token(self, monkeypatch, tmp_path):
        """Exit if the configured token environment variable is not set."""
        # Ensure G_T is not set
        monkeypatch.delenv("G_T", raising=False)

        # Set sys.argv to simulate CLI invocation
        monkeypatch.setattr(sys, "argv", ["blog-gen"])

        # Create a fake config.yaml so settings can load
        monkeypatch.chdir(tmp_path)
        config_content = """github:
  repo: user/repo
blog:
  title: Test Blog
  url: https://example.com
  author: Test
about:
  bio: Test bio
"""
        (tmp_path / "config.yaml").write_text(config_content)

        # Run CLI and expect SystemExit
        with pytest.raises(SystemExit) as exc_info:
            run_cli()

        # Should exit with code 1 (no token)
        assert exc_info.value.code == 1

    def test_cli_uses_g_t_env_token(self, monkeypatch, tmp_path):
        """Token is read from G_T environment variable."""
        test_token = "ghp_testtoken123"  # noqa: S105

        # Set G_T env var
        monkeypatch.setenv("G_T", test_token)

        # Set sys.argv to simulate CLI invocation
        monkeypatch.setattr(sys, "argv", ["blog-gen"])

        # Create a fake config.yaml in tmp_path and chdir there
        monkeypatch.chdir(tmp_path)
        config_content = """github:
  repo: user/repo
blog:
  title: Test Blog
  url: https://example.com
  author: Test
about:
  bio: Test bio
"""
        (tmp_path / "config.yaml").write_text(config_content)

        # Mock BlogGenerator to capture what was passed
        with patch("github_blog.cli.BlogGenerator") as mock_generator_class:
            mock_generator = MagicMock()
            mock_generator_class.return_value = mock_generator

            run_cli()

            # Verify BlogGenerator was called with the token from G_T and settings
            call_args = mock_generator_class.call_args
            assert call_args.args[0] == test_token
            assert call_args.args[1] == "user/repo"
            assert call_args.args[2] is not None
            mock_generator.generate.assert_called_once()

    def test_cli_repo_from_config(self, monkeypatch, tmp_path):
        """Repo is read from config.yaml when not provided via CLI."""
        test_token = "ghp_testtoken456"  # noqa: S105

        # Set G_T env var
        monkeypatch.setenv("G_T", test_token)

        # Set sys.argv to simulate CLI invocation
        monkeypatch.setattr(sys, "argv", ["blog-gen"])

        # Create config.yaml with specific repo
        config_repo = "myorg/myrepo"
        config_content = f"""github:
  repo: {config_repo}
blog:
  title: Test Blog
  url: https://example.com
  author: Test
about:
  bio: Test bio
"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text(config_content)

        # Mock BlogGenerator
        with patch("github_blog.cli.BlogGenerator") as mock_generator_class:
            mock_generator = MagicMock()
            mock_generator_class.return_value = mock_generator

            run_cli()

            # Verify BlogGenerator was called with repo from config
            call_args = mock_generator_class.call_args
            assert call_args.args[0] == test_token
            assert call_args.args[1] == config_repo
            assert call_args.args[2] is not None
            mock_generator.generate.assert_called_once()

    def test_cli_repo_cli_override(self, monkeypatch, tmp_path):
        """--repo CLI flag overrides repo from config.yaml."""
        test_token = "ghp_testtoken789"  # noqa: S105

        # Set G_T env var
        monkeypatch.setenv("G_T", test_token)

        # Override repo via CLI
        cli_repo = "override/override-repo"

        # Set sys.argv to simulate CLI invocation with --repo flag
        monkeypatch.setattr(sys, "argv", ["blog-gen", "--repo", cli_repo])

        # Create config.yaml with one repo (should be overridden)
        config_repo = "original/original-repo"
        config_content = f"""github:
  repo: {config_repo}
blog:
  title: Test Blog
  url: https://example.com
  author: Test
about:
  bio: Test bio
"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text(config_content)

        # Mock BlogGenerator
        with patch("github_blog.cli.BlogGenerator") as mock_generator_class:
            mock_generator = MagicMock()
            mock_generator_class.return_value = mock_generator

            run_cli()

            # Verify BlogGenerator was called with CLI repo, not config repo
            call_args = mock_generator_class.call_args
            assert call_args.args[0] == test_token
            assert call_args.args[1] == cli_repo
            assert call_args.args[2] is not None
            mock_generator.generate.assert_called_once()
