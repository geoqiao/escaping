import os
import shutil
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
    # Use different timestamps to ensure stable sorting (newest first)
    issue.created_at = datetime(2024, 1, number, tzinfo=timezone.utc)
    issue.updated_at = datetime(2024, 1, number, tzinfo=timezone.utc)
    return issue


@patch("github_blog.cli.GitHubService")
@patch("github_blog.cli.get_settings")
def test_blog_generator_integration(mock_get_settings, mock_gh_service_class, tmp_path):
    # Get absolute path to the project root to find real templates
    project_root = Path(__file__).parent.parent.absolute()
    # Use BearMinimal theme (the current default) for integration test
    real_template_path = project_root / "templates" / "BearMinimal"
    real_seo_path = project_root / "templates" / "seo"

    # Ensure we're in the project root directory for config loading
    old_cwd = os.getcwd()
    if not Path("config.yaml").exists():
        os.chdir(project_root)

    # Setup mock settings
    mock_settings = MagicMock()
    mock_settings.advanced.page_size = 2
    mock_settings.advanced.home_post_count = 10
    mock_settings.blog.url = "https://example.com"
    mock_settings.blog.title = "Test Blog"
    mock_settings.blog.description = "Test Description"
    mock_settings.blog.author = "Author"
    mock_settings.github.name = "user"
    mock_settings.github.repo = "user/repo"
    # Use the absolute path to real templates
    mock_settings.theme.path = str(real_template_path)
    mock_settings.theme.url_path = "/templates/BearMinimal"
    mock_settings.google_search_console.content = ""
    mock_settings.about.avatar = ""
    mock_settings.about.bio = "Test bio"
    mock_settings.about.expertise = ["Skill 1", "Skill 2"]
    mock_settings.about.links = []
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
                if "templates/BearMinimal" in path_str or "BearMinimal" in path_str:
                    return FileSystemLoader(str(real_template_path))
                return FileSystemLoader(path)

            mock_loader.side_effect = side_effect

            # Re-initialize to apply the mock during RenderService.__init__
            generator = BlogGenerator("fake-token", "user/repo")
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
    finally:
        os.chdir(old_cwd)
        # Cleanup: remove the output directory if it exists in project root
        project_output = project_root / "output"
        if project_output.exists():
            shutil.rmtree(project_output)
