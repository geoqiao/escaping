"""Tests for the 8-section Pydantic config models."""

from pathlib import Path

import pytest
from pydantic import ValidationError


class TestGithubConfig:
    """Tests for GithubConfig section."""

    def test_repo_required(self):
        """repo field is required."""
        from github_blog.config import GithubConfig

        cfg = GithubConfig(repo="geoqiao/blog")
        assert cfg.repo == "geoqiao/blog"

    def test_username_auto_parsed(self):
        """username is auto-parsed from repo."""
        from github_blog.config import GithubConfig

        cfg = GithubConfig(repo="geoqiao/blog")
        assert cfg.username == "geoqiao"

    def test_resolve_username_method(self):
        """resolve_username returns username."""
        from github_blog.config import GithubConfig

        cfg = GithubConfig(repo="geoqiao/blog")
        assert cfg.resolve_username() == "geoqiao"

    def test_repo_format_validation(self):
        """repo must contain a slash."""
        from github_blog.config import GithubConfig

        # Valid repos have slashes
        cfg = GithubConfig(repo="geoqiao/geoqiao.github.io")
        assert "/" in cfg.repo

    def test_github_config_invalid_repo(self):
        """Test invalid repo format raises error."""
        from github_blog.config import GithubConfig

        with pytest.raises(ValidationError):
            GithubConfig(repo="invalid-no-slash")


class TestBlogConfig:
    """Tests for BlogConfig section."""

    def test_required_fields(self):
        """title, url, and author are required."""
        from github_blog.config import BlogConfig

        cfg = BlogConfig(
            title="My Blog",
            url="https://example.com",
            author="John Doe",
        )
        assert cfg.title == "My Blog"
        assert cfg.url.scheme == "https"
        assert cfg.author == "John Doe"

    def test_url_is_htturl(self):
        """url is validated as HttpUrl."""
        from github_blog.config import BlogConfig

        cfg = BlogConfig(
            title="Test",
            url="https://example.com",
            author="Author",
        )
        assert cfg.url.scheme == "https"
        assert cfg.url.host == "example.com"


class TestAboutLink:
    """Tests for nested AboutLink model."""

    def test_name_and_url(self):
        """AboutLink has name and url."""
        from github_blog.config import AboutLink

        link = AboutLink(name="GitHub", url="https://github.com/user")
        assert link.name == "GitHub"
        assert link.url == "https://github.com/user"


class TestAboutConfig:
    """Tests for AboutConfig section."""

    def test_required_bio(self):
        """bio is required."""
        from github_blog.config import AboutConfig

        cfg = AboutConfig(bio="Hello world", links=[])
        assert cfg.bio == "Hello world"

    def test_optional_avatar(self):
        """avatar defaults to empty string."""
        from github_blog.config import AboutConfig

        cfg = AboutConfig(bio="Hello", links=[])
        assert cfg.avatar == ""

    def test_avatar_can_be_set(self):
        """avatar can be set to a URL."""
        from github_blog.config import AboutConfig

        cfg = AboutConfig(
            avatar="https://github.com/user.png",
            bio="Hello",
            links=[],
        )
        assert cfg.avatar == "https://github.com/user.png"

    def test_expertise_defaults_to_empty_list(self):
        """expertise defaults to empty list."""
        from github_blog.config import AboutConfig

        cfg = AboutConfig(bio="Hello", links=[])
        assert cfg.expertise == []

    def test_expertise_can_be_list(self):
        """expertise can be a list of strings."""
        from github_blog.config import AboutConfig

        cfg = AboutConfig(
            bio="Hello",
            expertise=["Python", "JavaScript"],
            links=[],
        )
        assert cfg.expertise == ["Python", "JavaScript"]

    def test_links_as_list_of_aboutlink(self):
        """links is a list of AboutLink objects."""
        from github_blog.config import AboutConfig, AboutLink

        cfg = AboutConfig(
            bio="Hello",
            links=[
                AboutLink(name="GitHub", url="https://github.com/user"),
                AboutLink(name="Twitter", url="https://twitter.com/user"),
            ],
        )
        assert len(cfg.links) == 2
        assert cfg.links[0].name == "GitHub"


class TestBrandingConfig:
    """Tests for BrandingConfig section."""

    def test_defaults(self):
        """All branding fields have sensible defaults."""
        from github_blog.config import BrandingConfig

        cfg = BrandingConfig()
        assert cfg.show_powered_by is True
        assert cfg.powered_by_text == "Powered by"
        assert cfg.powered_by_url == "https://github.com/geoqiao/github-blog"
        assert cfg.show_intro is False
        assert cfg.intro_text == ""
        assert cfg.source_link_text == "View Source"
        assert cfg.source_link_url == ""

    def test_all_fields_can_be_set(self):
        """All branding fields can be customized."""
        from github_blog.config import BrandingConfig

        cfg = BrandingConfig(
            show_powered_by=True,
            powered_by_text="Built with",
            powered_by_url="https://example.com",
            show_intro=True,
            intro_text="Welcome to my blog",
            source_link_text="Source Code",
            source_link_url="https://github.com/user/repo",
        )
        assert cfg.show_powered_by is True
        assert cfg.powered_by_text == "Built with"
        assert cfg.powered_by_url == "https://example.com"
        assert cfg.show_intro is True
        assert cfg.intro_text == "Welcome to my blog"
        assert cfg.source_link_text == "Source Code"
        assert cfg.source_link_url == "https://github.com/user/repo"


class TestPathsConfig:
    """Tests for PathsConfig section."""

    def test_defaults(self):
        """All path fields have defaults."""
        from github_blog.config import PathsConfig

        cfg = PathsConfig()
        assert cfg.output == "output"
        assert cfg.theme == "Escape1"
        assert cfg.blog == "blog"
        assert cfg.tag == "tag"
        assert cfg.rss == "atom.xml"
        assert cfg.about == "about.html"
        assert cfg.page_size == 10
        assert cfg.home_post_count == 10
        assert cfg.language == "en"

    def test_all_fields_can_be_set(self):
        """All path fields can be customized."""
        from github_blog.config import PathsConfig

        cfg = PathsConfig(
            output="public",
            theme="PaperMint",
            blog="posts",
            tag="topics",
            rss="feed.xml",
            about="me.html",
            page_size=20,
            home_post_count=15,
            language="zh-CN",
        )
        assert cfg.output == "public"
        assert cfg.theme == "PaperMint"
        assert cfg.blog == "posts"
        assert cfg.tag == "topics"
        assert cfg.rss == "feed.xml"
        assert cfg.about == "me.html"
        assert cfg.page_size == 20
        assert cfg.home_post_count == 15
        assert cfg.language == "zh-CN"

    def test_theme_path_property(self):
        """theme_path returns Path to theme directory."""
        from github_blog.config import PathsConfig

        cfg = PathsConfig(theme="Escape1")
        assert cfg.theme_path == Path("templates/Escape1")

    def test_seo_path_property(self):
        """seo_path returns Path to SEO templates."""
        from github_blog.config import PathsConfig

        cfg = PathsConfig()
        assert cfg.seo_path == Path("templates/seo")

    def test_theme_url_path_property(self):
        """theme_url_path returns URL path for theme assets."""
        from github_blog.config import PathsConfig

        cfg = PathsConfig(theme="Escape1")
        assert cfg.theme_url_path == "/templates/Escape1"


class TestSeoConfig:
    """Tests for SeoConfig section."""

    def test_defaults(self):
        """SEO fields have sensible defaults."""
        from github_blog.config import SeoConfig

        cfg = SeoConfig()
        assert cfg.google_search_console == ""
        assert cfg.enable_sitemap is True
        assert cfg.enable_robots is True

    def test_all_fields_can_be_set(self):
        """All SEO fields can be customized."""
        from github_blog.config import SeoConfig

        cfg = SeoConfig(
            google_search_console="DRggZlykSzc8M9TyaS0BPSRE7Kvw8W9hHt5pZrIMm3Y",
            enable_sitemap=False,
            enable_robots=False,
        )
        assert (
            cfg.google_search_console == "DRggZlykSzc8M9TyaS0BPSRE7Kvw8W9hHt5pZrIMm3Y"
        )
        assert cfg.enable_sitemap is False
        assert cfg.enable_robots is False


class TestCommentsConfig:
    """Tests for CommentsConfig section."""

    def test_defaults(self):
        """Comments fields have sensible defaults."""
        from github_blog.config import CommentsConfig

        cfg = CommentsConfig()
        assert cfg.provider == "utterances"
        assert cfg.repo == ""
        assert cfg.theme == "github-light"

    def test_all_fields_can_be_set(self):
        """All comments fields can be customized."""
        from github_blog.config import CommentsConfig

        cfg = CommentsConfig(
            provider="utterances",
            repo="user/repo",
            theme="github-dark",
        )
        assert cfg.provider == "utterances"
        assert cfg.repo == "user/repo"
        assert cfg.theme == "github-dark"


class TestSecurityConfig:
    """Tests for SecurityConfig section."""

    def test_defaults(self):
        """Security fields have sensible defaults."""
        from github_blog.config import SecurityConfig

        cfg = SecurityConfig()
        assert cfg.token_env == "G_T"  # noqa: S105

    def test_token_env_can_be_customized(self):
        """token_env can be customized."""
        from github_blog.config import SecurityConfig

        cfg = SecurityConfig(token_env="MY_TOKEN")  # noqa: S106
        assert cfg.token_env == "MY_TOKEN"  # noqa: S105


class TestSettings:
    """Tests for Settings class."""

    def test_load_from_yaml(self, tmp_path):
        """Settings can load from a YAML file."""
        from github_blog.config import Settings

        yaml_content = """
blog:
  title: Test Blog
  url: https://test.com
  author: Test Author

github:
  repo: testuser/testrepo

about:
  bio: Test bio
  links: []
"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml_content)

        settings = Settings.load_from_yaml(yaml_file)
        assert settings.blog.title == "Test Blog"
        assert settings.github.repo == "testuser/testrepo"

    def test_all_8_sections_present(self):
        """Settings has all 8 config sections."""
        from github_blog.config import Settings

        settings = Settings(
            blog={
                "title": "Test",
                "url": "https://example.com",
                "author": "Test",
            },
            github={"repo": "user/repo"},
            about={"bio": "Test"},
        )
        # Check all 8 sections exist
        assert hasattr(settings, "github")
        assert hasattr(settings, "blog")
        assert hasattr(settings, "about")
        assert hasattr(settings, "branding")
        assert hasattr(settings, "paths")
        assert hasattr(settings, "seo")
        assert hasattr(settings, "comments")
        assert hasattr(settings, "security")

    def test_extra_fields_ignored(self, tmp_path):
        """Extra fields in YAML are ignored."""
        from github_blog.config import Settings

        yaml_content = """
blog:
  title: Test Blog
  url: https://test.com
  author: Test Author

github:
  repo: testuser/testrepo

about:
  bio: Test bio
  links: []

unknown_field: this_should_be_ignored
another_unknown: 123
"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml_content)

        # Should not raise ValidationError
        settings = Settings.load_from_yaml(yaml_file)
        assert settings.blog.title == "Test Blog"
