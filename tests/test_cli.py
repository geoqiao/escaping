from __future__ import annotations

import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from github_blog.cli import BlogGenerator, run_cli


def _make_mock_issue(
    number: int, title: str, body: str = "body", labels: list[str] | None = None
) -> MagicMock:
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
def test_blog_generator_integration(
    mock_gh_service_class: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Get absolute path to the project root to find real templates
    project_root = Path(__file__).parent.parent.absolute()
    # Use Escape1 theme (the current default) for integration test
    real_template_path = project_root / "templates" / "Escape1"
    real_seo_path = project_root / "templates" / "seo"

    # Setup mock settings
    mock_settings = MagicMock()
    mock_settings.paths.page_size = 2
    mock_settings.paths.output = "output"
    mock_settings.paths.blog = "blog"
    mock_settings.paths.tag = "tag"
    mock_settings.paths.page = "page"
    mock_settings.paths.about = "about.html"
    mock_settings.paths.rss = "atom.xml"
    mock_settings.site.url = "https://example.com"
    mock_settings.site.title = "Test Blog"
    mock_settings.site.description = "Test Description"
    mock_settings.site.author = "Author"
    mock_settings.site.language = "en"
    mock_settings.github.username = "user"
    mock_settings.github.repo = "user/repo"
    # Use the absolute path to real templates
    mock_settings.paths.theme = "Escape1"
    mock_settings.paths.theme_path = real_template_path
    mock_settings.paths.theme_url_path = "/templates/Escape1"
    mock_settings.paths.theme_static_dst = Path("output/templates/Escape1/static")
    mock_settings.paths.theme_images_dst = Path("output/templates/Escape1/images")
    mock_settings.paths.seo_path = str(real_seo_path)
    mock_settings.seo.google_search_console = ""
    mock_settings.profile.avatar = ""
    mock_settings.profile.bio = "Test bio"
    mock_settings.profile.links = []
    mock_settings.site.navigation.items = []
    mock_settings.branding.show_powered_by = True
    mock_settings.branding.powered_by_text = "Powered by"
    mock_settings.branding.powered_by_url = "https://github.com/geoqiao/github-blog"
    mock_settings.branding.show_intro = False
    mock_settings.branding.intro_text = ""
    mock_settings.branding.intro_text2 = (
        "Generated with Python + Jinja2, deployed via GitHub Actions."
    )
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
    monkeypatch.chdir(tmp_path)

    try:
        # We need to mock RenderService because its __init__ hardcodes "templates/seo"
        # and it's called during BlogGenerator.__init__
        with patch(
            "github_blog.services.render_service.FileSystemLoader"
        ) as mock_loader:
            from jinja2 import FileSystemLoader

            def side_effect(path: str | Path) -> FileSystemLoader:
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

        # Verify legacy detail pages at .html paths (Ticket04 is tracer-only;
        # the default pipeline must NOT cut over to strict directory-index routes).
        blog_dir = output_dir / "blog"
        assert (blog_dir / "1-post-one.html").exists()
        assert (blog_dir / "2-post-two.html").exists()
        assert (blog_dir / "index.html").exists()
        assert (blog_dir / "page" / "1.html").exists()
        # Strict directory-index paths must NOT exist
        assert not (blog_dir / "my-first-post").exists()
        assert not (blog_dir / "second-post").exists()
        assert (output_dir / "index.html").exists()
        assert (output_dir / "tag" / "python.html").exists()
        assert (output_dir / "tag" / "web.html").exists()
        assert (output_dir / "atom.xml").exists()

        # Verify output root files
        assert (output_dir / "sitemap.xml").exists()
        assert (output_dir / "robots.txt").exists()

        # Verify content of index.html for correct slugs (legacy paths use title-based slugs)
        index_content = (output_dir / "index.html").read_text()
        assert "/blog/1-post-one.html" in index_content
        assert "/blog/2-post-two.html" in index_content

        # Legacy archive adapter keeps the existing artifacts and .html links,
        # while using a canonical that matches the primary page-one artifact.
        archive_content = (blog_dir / "index.html").read_text()
        assert 'href="https://example.com/blog/"' in archive_content
        assert 'href="/blog/1-post-one.html"' in archive_content
        assert 'href="/blog/2-post-two.html"' in archive_content

        # Verify legacy detail page canonical path matches the .html file writer
        post1_content = (blog_dir / "1-post-one.html").read_text()
        assert "Post One" in post1_content
        assert "/blog/1-post-one.html" in post1_content
        # Strict canonical (/blog/{slug}/) must NOT appear in legacy detail pages
        assert "/blog/1-post-one/" not in post1_content

        # Legacy detail tag href must point to the actual generated legacy
        # tag file, not the strict /tags/{key}/ route.
        assert 'href="/tag/python.html"' in post1_content
        assert "/tags/python/" not in post1_content
        # The referenced legacy tag file must actually exist on disk
        assert (output_dir / "tag" / "python.html").exists()

        post2_content = (blog_dir / "2-post-two.html").read_text()
        assert 'href="/tag/python.html"' in post2_content
        assert 'href="/tag/web.html"' in post2_content
        assert (output_dir / "tag" / "web.html").exists()

        # Verify theme static assets were copied into output
        theme_static_dir = output_dir / "templates" / "Escape1" / "static"
        assert theme_static_dir.exists(), (
            "Theme static directory should be copied to output"
        )
        assert (theme_static_dir / "css" / "style.css").exists(), (
            "Theme CSS should be present"
        )
        # Escape1 images live under static/images, not a top-level images/ folder
        theme_images_dir = output_dir / "templates" / "Escape1" / "images"
        assert not theme_images_dir.exists(), (
            "Top-level images dir should not be created when theme lacks it"
        )
        assert (theme_static_dir / "images" / "favicon.png").exists(), (
            "Favicon inside static/images should be present"
        )
    finally:
        # Cleanup: remove the output directory if it exists in project root
        project_output = project_root / "output"
        if project_output.exists():
            shutil.rmtree(project_output)


def test_legacy_generate_index_writes_empty_archive(tmp_path: Path) -> None:
    """Legacy writer still emits intentional page-one artifacts when empty."""
    settings = MagicMock()
    settings.paths.output = "output"
    settings.paths.blog = "blog"
    settings.paths.page = "page"
    settings.paths.page_size = 10
    render_service = MagicMock()
    render_service.render_index.return_value = "<html>Empty archive</html>"
    generator = BlogGenerator(
        "fake-token",
        "user/repo",
        settings,
        github_service=MagicMock(),
        render_service=render_service,
    )
    generator._build_dir = tmp_path

    generator._generate_index([], [], {})

    assert (tmp_path / "blog" / "index.html").read_text() == (
        "<html>Empty archive</html>"
    )
    assert (tmp_path / "blog" / "page" / "1.html").read_text() == (
        "<html>Empty archive</html>"
    )
    render_service.render_index.assert_called_once_with(
        [],
        [],
        {
            "page": 1,
            "pages": 1,
            "has_prev": False,
            "has_next": False,
            "prev_num": 0,
            "next_num": 2,
        },
        {},
    )


class TestNewCLI:
    """Tests for the new CLI behavior (token from G_T env, repo from config or --repo flag)."""

    def test_cli_requires_token(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Exit if the configured token environment variable is not set."""
        # Ensure G_T is not set
        monkeypatch.delenv("G_T", raising=False)

        # Set sys.argv to simulate CLI invocation
        monkeypatch.setattr(sys, "argv", ["blog-gen"])

        # Create a fake config.yaml so settings can load
        monkeypatch.chdir(tmp_path)
        config_content = """github:
  repo: user/repo
  allowed_authors:
    - user
site:
  title: Test Blog
  url: https://example.com
  author: Test
about:
  issue_number: 1
security:
  token_env: G_T
"""
        (tmp_path / "config.yaml").write_text(config_content)

        # Run CLI and expect SystemExit
        with pytest.raises(SystemExit) as exc_info:
            run_cli()

        # Should exit with code 1 (no token)
        assert exc_info.value.code == 1

    def test_cli_uses_g_t_env_token(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
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
  allowed_authors:
    - user
site:
  title: Test Blog
  url: https://example.com
  author: Test
about:
  issue_number: 1
security:
  token_env: G_T
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

    def test_cli_repo_from_config(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
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
  allowed_authors:
    - myorg
site:
  title: Test Blog
  url: https://example.com
  author: Test
about:
  issue_number: 1
security:
  token_env: G_T
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

    def test_cli_repo_cli_override(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
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
  allowed_authors:
    - original
site:
  title: Test Blog
  url: https://example.com
  author: Test
about:
  issue_number: 1
security:
  token_env: G_T
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

    def test_cli_repo_override_validates_and_propagates(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """--repo override is validated with GithubConfig rules and propagates
        to settings.github so context/fallback use it everywhere."""
        test_token = "ghp_testtoken000"  # noqa: S105
        monkeypatch.setenv("G_T", test_token)

        cli_repo = "userB/repoB"
        monkeypatch.setattr(sys, "argv", ["blog-gen", "--repo", cli_repo])

        config_content = """github:
  repo: userA/repoA
  allowed_authors:
    - userA
site:
  title: Test Blog
  url: https://example.com
  author: Test
about:
  issue_number: 1
security:
  token_env: G_T
"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text(config_content)

        with patch("github_blog.cli.BlogGenerator") as mock_generator_class:
            mock_generator = MagicMock()
            mock_generator_class.return_value = mock_generator

            run_cli()

            call_args = mock_generator_class.call_args
            settings = call_args.args[2]
            # Override propagated to settings.github
            assert settings.github.repo == "userB/repoB"
            assert settings.github.username == "userB"
            # allowed_authors preserved from config
            assert settings.github.allowed_authors == ["userA"]
            # Comments fallback uses override repo
            assert (settings.comments.repo or settings.github.repo) == "userB/repoB"

    def test_cli_invalid_repo_override_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """An invalid --repo format must raise ValidationError, not proceed."""
        from pydantic import ValidationError

        test_token = "ghp_testtoken111"  # noqa: S105
        monkeypatch.setenv("G_T", test_token)

        monkeypatch.setattr(sys, "argv", ["blog-gen", "--repo", "invalid-no-slash"])

        config_content = """github:
  repo: userA/repoA
  allowed_authors:
    - userA
site:
  title: Test Blog
  url: https://example.com
  author: Test
about:
  issue_number: 1
security:
  token_env: G_T
"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text(config_content)

        with pytest.raises(ValidationError, match="owner/repo"):
            run_cli()


def test_copy_theme_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit test for _copy_theme_assets covering both static/ and images/ branches."""
    from github_blog.cli import BlogGenerator

    monkeypatch.chdir(tmp_path)

    # Create a fake theme directory with static and images subdirectories
    theme_dir = tmp_path / "templates" / "FakeTheme"
    static_dir = theme_dir / "static"
    static_dir.mkdir(parents=True)
    (static_dir / "style.css").write_text("body {}")

    images_dir = theme_dir / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "favicon.png").write_text("fake png")

    mock_settings = MagicMock()
    mock_settings.paths.output = "output"
    mock_settings.paths.theme = "FakeTheme"
    mock_settings.paths.theme_path = theme_dir

    generator = BlogGenerator("fake-token", "user/repo", mock_settings)
    generator._copy_theme_assets()

    assert (
        tmp_path / "output" / "templates" / "FakeTheme" / "static" / "style.css"
    ).exists()
    assert (
        tmp_path / "output" / "templates" / "FakeTheme" / "images" / "favicon.png"
    ).exists()


class TestCompilerOutputSafety:
    """An unsafe output config must fail before _init_dirs, rendering, copying, or writes."""

    @patch("github_blog.cli.GitHubService")
    def test_unsafe_output_root_fails_before_init_dirs(
        self,
        mock_gh_service_class: MagicMock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An output root outside the allowed set must fail before any mutation.

        This test creates a real Settings with ``paths.output: src`` (a
        protected root) and verifies that ``generate()`` exits before
        ``_init_dirs`` is reached - no files are deleted or created.
        """
        from github_blog.config import Settings

        monkeypatch.chdir(tmp_path)

        # Create a "src" directory with an important file to prove it survives.
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        important = src_dir / "important.py"
        important.write_text("# important")

        # Load a real Settings object with an unsafe output root.
        config_content = """
github:
  repo: user/repo
  allowed_authors:
    - user
site:
  title: Test Blog
  url: https://example.com/
  author: Test
about:
  issue_number: 1
security:
  token_env: G_T
paths:
  output: src
"""
        (tmp_path / "config.yaml").write_text(config_content)
        settings = Settings.load_from_yaml(tmp_path / "config.yaml")

        # Mock GitHubService so no real API calls are made.
        mock_gh = mock_gh_service_class.return_value
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        mock_gh.get_user_issues.return_value = []

        generator = BlogGenerator("fake-token", "user/repo", settings)

        result = generator.generate()
        assert not result.success

        # The important file must still exist - _init_dirs was NOT called.
        assert important.exists()
        assert important.read_text() == "# important"

        # No output files should have been created in src/.
        assert not (src_dir / "index.html").exists()
        assert not (src_dir / "atom.xml").exists()
        assert not (src_dir / "sitemap.xml").exists()
        assert not (src_dir / "blog").exists()
        assert not (src_dir / "tag").exists()

    @patch("github_blog.cli.GitHubService")
    def test_symlink_output_fails_before_init_dirs(
        self,
        mock_gh_service_class: MagicMock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A symlink output root must fail before any mutation."""
        import os

        from github_blog.config import Settings

        monkeypatch.chdir(tmp_path)

        # Create a real directory and a symlink pointing to it (inside repo).
        real_output = tmp_path / "real_output"
        real_output.mkdir()
        (real_output / "keep.txt").write_text("keep")

        link = tmp_path / "output"
        os.symlink(real_output, link)

        config_content = """
github:
  repo: user/repo
  allowed_authors:
    - user
site:
  title: Test Blog
  url: https://example.com/
  author: Test
about:
  issue_number: 1
security:
  token_env: G_T
"""
        (tmp_path / "config.yaml").write_text(config_content)
        settings = Settings.load_from_yaml(tmp_path / "config.yaml")

        mock_gh = mock_gh_service_class.return_value
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        mock_gh.get_user_issues.return_value = []

        generator = BlogGenerator("fake-token", "user/repo", settings)

        result = generator.generate()
        assert not result.success

        # The symlink target's contents must survive.
        assert (real_output / "keep.txt").exists()
        assert (real_output / "keep.txt").read_text() == "keep"
        # No output files created through the symlink.
        assert not (real_output / "index.html").exists()

    @patch("github_blog.cli.GitHubService")
    def test_malicious_label_fails_before_init_dirs(
        self,
        mock_gh_service_class: MagicMock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A label-derived tag with path-escaping components must fail before _init_dirs.

        Malicious labels containing ``/``, ``\\``, ``.``/``..`` or escaping
        components must be rejected before output deletion or rendering.
        This regression proves existing output survives.
        """
        from github_blog.config import Settings

        monkeypatch.chdir(tmp_path)

        # Create existing output with a file that must survive.
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "keep.txt").write_text("survive")

        config_content = """
github:
  repo: user/repo
  allowed_authors:
    - user
site:
  title: Test Blog
  url: https://example.com/
  author: Test
about:
  issue_number: 1
security:
  token_env: G_T
"""
        (tmp_path / "config.yaml").write_text(config_content)
        settings = Settings.load_from_yaml(tmp_path / "config.yaml")

        mock_gh = mock_gh_service_class.return_value
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        mock_gh.get_user_issues.return_value = [
            _make_mock_issue(1, "Safe Title", labels=["../../etc/passwd"]),
        ]

        generator = BlogGenerator("fake-token", "user/repo", settings)

        result = generator.generate()
        assert not result.success

        # Existing output must survive - _init_dirs was NOT called.
        assert (output_dir / "keep.txt").exists()
        assert (output_dir / "keep.txt").read_text() == "survive"
        # No new files created.
        assert not (output_dir / "index.html").exists()
        assert not (output_dir / "blog").exists()
        assert not (output_dir / "tag").exists()

    @patch("github_blog.cli.GitHubService")
    @pytest.mark.parametrize(
        "malicious_label",
        [
            "foo/bar",
            "foo\\bar",
            ".",
            "..",
            "../etc",
            "/etc/passwd",
        ],
    )
    def test_malicious_labels_rejected(
        self,
        mock_gh_service_class: MagicMock,
        malicious_label: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Each malicious label variant must fail before filesystem mutation."""
        from github_blog.config import Settings

        monkeypatch.chdir(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "keep.txt").write_text("survive")

        config_content = """
github:
  repo: user/repo
  allowed_authors:
    - user
site:
  title: Test Blog
  url: https://example.com/
  author: Test
about:
  issue_number: 1
security:
  token_env: G_T
"""
        (tmp_path / "config.yaml").write_text(config_content)
        settings = Settings.load_from_yaml(tmp_path / "config.yaml")

        mock_gh = mock_gh_service_class.return_value
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        mock_gh.get_user_issues.return_value = [
            _make_mock_issue(1, "Title", labels=[malicious_label]),
        ]

        generator = BlogGenerator("fake-token", "user/repo", settings)

        result = generator.generate()
        assert not result.success

        assert (output_dir / "keep.txt").exists()
        assert (output_dir / "keep.txt").read_text() == "survive"
