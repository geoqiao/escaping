import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from github_blog.cli import BlogGenerator


def _make_mock_issue(number, title, body="body", labels=None):
    issue = MagicMock()
    issue.number = number
    issue.title = title
    issue.body = body
    label_mocks = []
    if labels:
        for l in labels:
            m = MagicMock()
            m.name = l
            label_mocks.append(m)
    issue.labels = label_mocks
    issue.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    issue.updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return issue


@patch("github_blog.cli.GitHubService")
@patch("github_blog.cli.get_settings")
def test_blog_generator_integration(mock_get_settings, mock_gh_service_class, tmp_path):
    # Get absolute path to the project root to find real templates
    project_root = Path(__file__).parent.parent.absolute()
    real_template_path = project_root / "templates" / "PaperMint"
    real_seo_path = project_root / "templates" / "seo"

    # Setup mock settings
    content_dir = tmp_path / "contents"
    mock_settings = MagicMock()
    mock_settings.blog.content_dir = content_dir
    mock_settings.blog.blog_dir = "blog"
    mock_settings.blog.page_size = 2
    mock_settings.blog.rss_atom_path = "atom.xml"
    mock_settings.blog.url = "https://example.com"
    mock_settings.blog.title = "Test Blog"
    mock_settings.blog.description = "Test Description"
    mock_settings.blog.author.name = "Author"
    mock_settings.blog.author.email = "author@example.com"
    mock_settings.github.name = "user"
    mock_settings.github.repo = "repo"
    # Use the absolute path to real templates
    mock_settings.theme.path = str(real_template_path)
    mock_settings.theme.url_path = "/templates/PaperMint"
    mock_settings.google_search_console.content = ""
    mock_get_settings.return_value = mock_settings

    # Setup mock GitHub service
    mock_gh_service = mock_gh_service_class.return_value
    mock_repo = MagicMock()
    mock_gh_service.get_repo.return_value = mock_repo

    issues = [
        _make_mock_issue(1, "Post One", labels=["python"]),
        _make_mock_issue(2, "Post Two", labels=["python", "web"]),
    ]
    mock_gh_service.get_user_issues.return_value = issues

    # Initialize and generate
    # We need to change CWD to tmp_path to avoid polluting the project root
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
                if "templates/PaperMint" in path_str or "PaperMint" in path_str:
                    return FileSystemLoader(str(real_template_path))
                return FileSystemLoader(path)

            mock_loader.side_effect = side_effect

            # Re-initialize to apply the mock during RenderService.__init__
            generator = BlogGenerator("fake-token", "user/repo")
            generator.generate()

        # Verify files were created in tmp_path/contents
        blog_dir = content_dir / "blog"
        assert (blog_dir / "1-python.html").exists()
        assert (blog_dir / "2-python-web.html").exists()
        assert (content_dir / "index.html").exists()
        assert (content_dir / "tag" / "python.html").exists()
        assert (content_dir / "tag" / "web.html").exists()
        assert (content_dir / "atom.xml").exists()

        # Verify project root files in tmp_path
        assert (tmp_path / "index.html").exists()
        assert (tmp_path / "sitemap.xml").exists()
        assert (tmp_path / "robots.txt").exists()

        # Verify content of index.html for correct slugs
        index_content = (content_dir / "index.html").read_text()
        assert "/contents/blog/1-python.html" in index_content
        assert "/contents/blog/2-python-web.html" in index_content
    finally:
        os.chdir(old_cwd)
