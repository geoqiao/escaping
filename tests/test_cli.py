"""Tests for the BlogGenerator CLI public contract."""

from __future__ import annotations

import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from github_blog.cli import BlogGenerator, run_cli

_PROJECT_ROOT = Path(__file__).parent.parent.absolute()


def _mock_issue(
    number: int, title: str, body: str = "body", labels: list[str] | None = None
) -> MagicMock:
    issue = MagicMock()
    issue.number = number
    issue.title = title
    issue.body = body
    issue.labels = []
    if labels:
        for name in labels:
            m = MagicMock()
            m.name = name
            issue.labels.append(m)
    issue.created_at = datetime(2024, 1, number, tzinfo=timezone.utc)
    issue.updated_at = datetime(2024, 1, number, tzinfo=timezone.utc)
    return issue


def _mock_settings(theme: str = "Escape1") -> MagicMock:
    """Mock settings wired to real templates for the given theme."""
    s = MagicMock()
    s.paths.page_size = 2
    s.paths.output = "output"
    s.paths.blog = "blog"
    s.paths.tag = "tag"
    s.paths.page = "page"
    s.paths.about = "about.html"
    s.paths.rss = "atom.xml"
    s.paths.theme = theme
    s.paths.theme_path = _PROJECT_ROOT / "templates" / theme
    s.paths.theme_url_path = f"/templates/{theme}"
    s.paths.theme_static_dst = Path(f"output/templates/{theme}/static")
    s.paths.theme_images_dst = Path(f"output/templates/{theme}/images")
    s.paths.seo_path = str(_PROJECT_ROOT / "templates" / "seo")
    s.site.url = "https://example.com"
    s.site.title = "Test Blog"
    s.site.description = "Test Description"
    s.site.author = "Author"
    s.site.language = "en"
    s.github.username = "user"
    s.github.repo = "user/repo"
    s.seo.google_search_console = ""
    s.profile.avatar = ""
    s.profile.bio = "Test bio"
    s.profile.links = []
    s.site.navigation.items = []
    s.branding.show_powered_by = True
    s.branding.powered_by_text = "Powered by"
    s.branding.powered_by_url = "https://github.com/geoqiao/github-blog"
    s.branding.show_intro = False
    s.branding.intro_text = ""
    s.branding.intro_text2 = (
        "Generated with Python + Jinja2, deployed via GitHub Actions."
    )
    s.branding.source_link_text = "View Source"
    s.branding.source_link_url = ""
    s.comments.provider = "utterances"
    s.comments.repo = ""
    s.comments.theme = "github-light"
    s.comments.theme_mode = "auto"
    return s


@pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
@patch("github_blog.cli.GitHubService")
def test_public_generate_full_legacy_artifact(
    mock_gh_class: MagicMock,
    theme: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Public generate() produces all legacy .html artifacts, RSS, sitemap,
    robots, and theme static assets for both themes."""
    mock_settings = _mock_settings(theme)
    real_tpl = _PROJECT_ROOT / "templates" / theme
    real_seo = _PROJECT_ROOT / "templates" / "seo"

    mock_gh = mock_gh_class.return_value
    mock_repo = MagicMock()
    mock_gh.get_repo.return_value = mock_repo
    issues = [
        _mock_issue(1, "Post One", labels=["python"]),
        _mock_issue(2, "Post Two", labels=["python", "web"]),
    ]
    mock_gh.get_user_issues.return_value = issues

    output_dir = tmp_path / "output"
    monkeypatch.chdir(tmp_path)

    try:
        from jinja2 import FileSystemLoader

        with patch(
            "github_blog.services.render_service.FileSystemLoader"
        ) as mock_loader:

            def side_effect(path: str | Path) -> FileSystemLoader:
                ps = str(path)
                if "templates/seo" in ps:
                    return FileSystemLoader(str(real_seo))
                return FileSystemLoader(str(real_tpl))

            mock_loader.side_effect = side_effect
            generator = BlogGenerator("fake-token", "user/repo", mock_settings)
            generator.generate()

        blog = output_dir / "blog"
        # Legacy .html detail pages.
        assert (blog / "1-post-one.html").exists()
        assert (blog / "2-post-two.html").exists()
        # Strict directory-index paths must NOT exist.
        assert not (blog / "1-post-one").exists()
        # Archive index + pagination.
        assert (blog / "index.html").exists()
        assert (blog / "page" / "1.html").exists()
        # Landing page.
        assert (output_dir / "index.html").exists()
        # Tag pages.
        assert (output_dir / "tag" / "python.html").exists()
        assert (output_dir / "tag" / "web.html").exists()
        # RSS, sitemap, robots.
        assert (output_dir / "atom.xml").exists()
        assert (output_dir / "sitemap.xml").exists()
        assert (output_dir / "robots.txt").exists()

        # Legacy hrefs in detail page.
        post1 = (blog / "1-post-one.html").read_text()
        assert "/blog/1-post-one.html" in post1
        assert "/blog/1-post-one/" not in post1
        assert 'href="/tag/python.html"' in post1
        assert "/tags/python/" not in post1

        # Theme static assets copied.
        assert (
            output_dir / "templates" / theme / "static" / "css" / "style.css"
        ).exists()
    finally:
        project_output = _PROJECT_ROOT / "output"
        if project_output.exists():
            shutil.rmtree(project_output)


@patch("github_blog.cli.GitHubService")
def test_empty_issues(
    mock_gh_class: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """generate() with zero issues still produces empty-state artifacts."""
    mock_settings = _mock_settings()
    real_tpl = _PROJECT_ROOT / "templates" / "Escape1"
    real_seo = _PROJECT_ROOT / "templates" / "seo"

    mock_gh = mock_gh_class.return_value
    mock_gh.get_repo.return_value = MagicMock()
    mock_gh.get_user_issues.return_value = []

    monkeypatch.chdir(tmp_path)

    from jinja2 import FileSystemLoader

    with patch("github_blog.services.render_service.FileSystemLoader") as mock_loader:

        def side_effect(path: str | Path) -> FileSystemLoader:
            ps = str(path)
            if "templates/seo" in ps:
                return FileSystemLoader(str(real_seo))
            return FileSystemLoader(str(real_tpl))

        mock_loader.side_effect = side_effect
        generator = BlogGenerator("fake-token", "user/repo", mock_settings)
        result = generator.generate()

    assert result.success
    output_dir = tmp_path / "output"
    assert (output_dir / "index.html").exists()
    assert (output_dir / "blog" / "index.html").exists()
    assert (output_dir / "atom.xml").exists()

    # Cleanup project root output if leaked.
    project_output = _PROJECT_ROOT / "output"
    if project_output.exists():
        shutil.rmtree(project_output)


class TestCLITokenAndRepo:
    _CONFIG = """\
github:
  repo: {repo}
  allowed_authors:
    - {author}
site:
  title: Test Blog
  url: https://example.com
  author: Test
about:
  issue_number: 1
security:
  token_env: {token_env}
"""

    def _setup(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        *,
        token_env: str = "G_T",  # noqa: S107
        repo: str = "user/repo",
        author: str = "user",
        cli_args: list[str] | None = None,
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["blog-gen", *(cli_args or [])])
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text(
            self._CONFIG.format(repo=repo, author=author, token_env=token_env)
        )

    def test_missing_custom_token_exits(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Missing configured token env var exits with code 1."""
        monkeypatch.delenv("G_T", raising=False)
        monkeypatch.delenv("CUSTOM_TOKEN", raising=False)
        self._setup(monkeypatch, tmp_path, token_env="CUSTOM_TOKEN")  # noqa: S106
        with pytest.raises(SystemExit) as exc:
            run_cli()
        assert exc.value.code == 1

    def test_custom_token_success_not_g_t(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Only CUSTOM_TOKEN is set (G_T is not); CLI reads the configured
        CUSTOM_TOKEN and succeeds."""
        token = "ghp_customtoken456"  # noqa: S105
        monkeypatch.setenv("CUSTOM_TOKEN", token)
        monkeypatch.delenv("G_T", raising=False)
        self._setup(monkeypatch, tmp_path, token_env="CUSTOM_TOKEN")  # noqa: S106
        with patch("github_blog.cli.BlogGenerator") as mock_gen:
            mock_gen.return_value = MagicMock()
            run_cli()
            assert mock_gen.call_args.args[0] == token

    def test_valid_repo_override_propagates(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """--repo override validates and propagates to settings.github."""
        monkeypatch.setenv("G_T", "ghp_x")
        self._setup(
            monkeypatch,
            tmp_path,
            repo="userA/repoA",
            author="userA",
            cli_args=["--repo", "userB/repoB"],
        )
        with patch("github_blog.cli.BlogGenerator") as mock_gen:
            mock_gen.return_value = MagicMock()
            run_cli()
            settings = mock_gen.call_args.args[2]
            assert settings.github.repo == "userB/repoB"
            assert settings.github.username == "userB"
            assert settings.github.allowed_authors == ["userA"]

    def test_invalid_repo_override_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Invalid --repo format raises ValidationError."""
        monkeypatch.setenv("G_T", "ghp_x")
        self._setup(monkeypatch, tmp_path, cli_args=["--repo", "invalid-no-slash"])
        with pytest.raises(ValidationError, match="owner/repo"):
            run_cli()


@patch("github_blog.cli.GitHubService")
def test_malicious_label_preserves_old_output(
    mock_gh_class: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A label with path-escaping components must fail before filesystem
    mutation; existing output survives."""
    from github_blog.config import Settings

    monkeypatch.chdir(tmp_path)
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "keep.txt").write_text("survive")

    (tmp_path / "config.yaml").write_text("""\
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
""")
    settings = Settings.load_from_yaml(tmp_path / "config.yaml")

    mock_gh = mock_gh_class.return_value
    mock_gh.get_repo.return_value = MagicMock()
    mock_gh.get_user_issues.return_value = [
        _mock_issue(1, "Safe Title", labels=["../../etc/passwd"]),
    ]

    result = BlogGenerator("fake-token", "user/repo", settings).generate()
    assert not result.success
    assert (output_dir / "keep.txt").exists()
    assert (output_dir / "keep.txt").read_text() == "survive"
    assert not (output_dir / "index.html").exists()
    assert not (output_dir / "blog").exists()
