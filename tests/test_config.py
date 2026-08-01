"""Strict configuration tests for the Ticket 02 config contract.

Every model rejects unknown fields (extra="forbid") at every nested level.
The config structure separates site identity from Site Profile, requires
non-empty allowed_authors, immutable About Issue selection, positive page
size with default 10, canonical HTTPS origin, dynamic token env, and strict
project/theme input references.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import HttpUrl, ValidationError

if TYPE_CHECKING:
    from github_blog.config import Settings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_yaml() -> str:
    """Return a minimal valid YAML string for all required sections."""
    return """
github:
  repo: geoqiao/geoqiao.github.io
  allowed_authors:
    - geoqiao

site:
  title: Test Blog
  url: https://example.com
  author: Test Author
  description: Test Description
  language: en

profile:
  avatar: https://github.com/geoqiao.png
  bio: Test bio
  links:
    - name: GitHub
      url: https://github.com/geoqiao

about:
  issue_number: 42

security:
  token_env: G_T
"""


def _load_settings(yaml_content: str, tmp_path: Path) -> Settings:
    from github_blog.config import Settings

    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(yaml_content)
    return Settings.load_from_yaml(yaml_file)


# ---------------------------------------------------------------------------
# Strict unknown-field rejection at every level
# ---------------------------------------------------------------------------


class TestStrictUnknownFields:
    """Unknown fields must fail at every nested configuration level."""

    def test_top_level_unknown_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match="unknown_field"):
            _load_settings(_base_yaml() + "unknown_field: bad\n", tmp_path)

    def test_github_unknown_rejected(self, tmp_path: Path) -> None:
        yaml = _base_yaml().replace(
            "  allowed_authors:\n    - geoqiao",
            "  allowed_authors:\n    - geoqiao\n  typo_field: bad",
        )
        with pytest.raises(ValidationError, match="typo_field"):
            _load_settings(yaml, tmp_path)

    def test_site_unknown_rejected(self, tmp_path: Path) -> None:
        yaml = _base_yaml().replace(
            "  language: en\n", "  language: en\n  mistyped: true\n", 1
        )
        with pytest.raises(ValidationError, match="mistyped"):
            _load_settings(yaml, tmp_path)

    def test_profile_unknown_rejected(self, tmp_path: Path) -> None:
        yaml = _base_yaml().replace(
            "  bio: Test bio\n", "  bio: Test bio\n  expertise: bad\n", 1
        )
        with pytest.raises(ValidationError, match="expertise"):
            _load_settings(yaml, tmp_path)

    def test_about_unknown_rejected(self, tmp_path: Path) -> None:
        yaml = _base_yaml().replace(
            "  issue_number: 42\n", "  issue_number: 42\n  extra: bad\n", 1
        )
        with pytest.raises(ValidationError, match="extra"):
            _load_settings(yaml, tmp_path)

    def test_paths_unknown_rejected(self, tmp_path: Path) -> None:
        yaml = _base_yaml() + "paths:\n  output: out\n  bad_field: x\n"
        with pytest.raises(ValidationError, match="bad_field"):
            _load_settings(yaml, tmp_path)

    def test_comments_unknown_rejected(self, tmp_path: Path) -> None:
        yaml = _base_yaml() + "comments:\n  provider: utterances\n  oops: 1\n"
        with pytest.raises(ValidationError, match="oops"):
            _load_settings(yaml, tmp_path)

    def test_security_unknown_rejected(self, tmp_path: Path) -> None:
        yaml = _base_yaml().replace(
            "  token_env: G_T\n", "  token_env: G_T\n  extra_sec: 1\n", 1
        )
        with pytest.raises(ValidationError, match="extra_sec"):
            _load_settings(yaml, tmp_path)

    def test_seo_unknown_rejected(self, tmp_path: Path) -> None:
        yaml = _base_yaml() + "seo:\n  enable_sitemap: true\n  seo_typo: x\n"
        with pytest.raises(ValidationError, match="seo_typo"):
            _load_settings(yaml, tmp_path)

    def test_branding_unknown_rejected(self, tmp_path: Path) -> None:
        yaml = _base_yaml() + "branding:\n  show_powered_by: true\n  bad: x\n"
        with pytest.raises(ValidationError, match="bad"):
            _load_settings(yaml, tmp_path)

    def test_navigation_unknown_rejected(self, tmp_path: Path) -> None:
        yaml = _base_yaml().replace(
            "  language: en\n",
            "  language: en\n  navigation:\n    items: []\n    bad_nav: x\n",
            1,
        )
        with pytest.raises(ValidationError, match="bad_nav"):
            _load_settings(yaml, tmp_path)

    def test_navigation_link_unknown_rejected(self, tmp_path: Path) -> None:
        yaml = _base_yaml().replace(
            "  language: en\n",
            "  language: en\n"
            "  navigation:\n"
            "    items:\n"
            "      - name: Blog\n        url: /blog/\n        extra_link: x\n",
            1,
        )
        with pytest.raises(ValidationError, match="extra_link"):
            _load_settings(yaml, tmp_path)

    def test_profile_link_unknown_rejected(self, tmp_path: Path) -> None:
        from github_blog.config import Settings

        yaml = """
github:
  repo: u/r
  allowed_authors: [u]
site:
  title: T
  url: https://x.com
  author: A
profile:
  bio: Test
  links:
    - name: GitHub
      url: https://github.com/u
      link_extra: x
about:
  issue_number: 1
security:
  token_env: G_T
"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml)
        with pytest.raises(ValidationError, match="link_extra"):
            Settings.load_from_yaml(yaml_file)

    def test_project_entry_unknown_rejected(self, tmp_path: Path) -> None:
        yaml = (
            _base_yaml() + "projects:\n  - slug: p\n    title: P\n    repository: r\n"
            "    summary: s\n    bad_proj: x\n"
        )
        with pytest.raises(ValidationError, match="bad_proj"):
            _load_settings(yaml, tmp_path)

    def test_project_fallback_metadata_unknown_rejected(self, tmp_path: Path) -> None:
        yaml = (
            _base_yaml() + "projects:\n  - slug: p\n    title: P\n    repository: r\n"
            "    summary: s\n    fallback_metadata:\n      stars: 10\n      bad_meta: x\n"
        )
        with pytest.raises(ValidationError, match="bad_meta"):
            _load_settings(yaml, tmp_path)

    def test_theme_lock_unknown_rejected(self, tmp_path: Path) -> None:
        yaml = (
            _base_yaml()
            + "theme_lock:\n  repository: org/theme\n  commit: "
            + "a" * 40
            + "\n  api_version: '1'\n  bad_theme: x\n"
        )
        with pytest.raises(ValidationError, match="bad_theme"):
            _load_settings(yaml, tmp_path)


# ---------------------------------------------------------------------------
# GithubConfig
# ---------------------------------------------------------------------------


class TestGithubConfig:
    def test_repo_required(self) -> None:
        from github_blog.config import GithubConfig

        with pytest.raises(ValidationError):
            GithubConfig(allowed_authors=["user"])  # type: ignore

    def test_repo_format_validated(self) -> None:
        from github_blog.config import GithubConfig

        with pytest.raises(ValidationError, match="owner/repo"):
            GithubConfig(repo="invalid-no-slash", allowed_authors=["user"])

    def test_username_derived_from_repo(self) -> None:
        from github_blog.config import GithubConfig

        cfg = GithubConfig(repo="geoqiao/blog", allowed_authors=["geoqiao"])
        assert cfg.username == "geoqiao"

    def test_allowed_authors_required(self, tmp_path: Path) -> None:
        yaml = """
github:
  repo: user/repo
site:
  title: T
  url: https://example.com
  author: A
about:
  issue_number: 1
security:
  token_env: G_T
"""
        with pytest.raises(ValidationError, match="allowed_authors"):
            _load_settings(yaml, tmp_path)

    def test_allowed_authors_empty_rejected(self, tmp_path: Path) -> None:
        yaml = """
github:
  repo: user/repo
  allowed_authors: []
site:
  title: T
  url: https://example.com
  author: A
about:
  issue_number: 1
security:
  token_env: G_T
"""
        with pytest.raises(ValidationError, match="allowed_authors"):
            _load_settings(yaml, tmp_path)

    def test_allowed_authors_accepts_list(self, tmp_path: Path) -> None:
        settings = _load_settings(_base_yaml(), tmp_path)
        assert settings.github.allowed_authors == ["geoqiao"]


# ---------------------------------------------------------------------------
# SiteConfig - site identity
# ---------------------------------------------------------------------------


class TestSiteConfig:
    def test_required_fields(self) -> None:
        from github_blog.config import SiteConfig

        cfg = SiteConfig(
            title="My Blog",
            url=HttpUrl("https://example.com"),
            author="Author",
        )
        assert cfg.title == "My Blog"
        assert cfg.author == "Author"
        assert cfg.url.scheme == "https"

    def test_description_optional(self) -> None:
        from github_blog.config import SiteConfig

        cfg = SiteConfig(title="T", url=HttpUrl("https://x.com"), author="A")
        assert cfg.description == ""

    def test_language_default(self) -> None:
        from github_blog.config import SiteConfig

        cfg = SiteConfig(title="T", url=HttpUrl("https://x.com"), author="A")
        assert cfg.language == "en"

    def test_language_can_be_set(self, tmp_path: Path) -> None:
        settings = _load_settings(_base_yaml(), tmp_path)
        assert settings.site.language == "en"

    def test_navigation_optional_with_default(self) -> None:
        from github_blog.config import SiteConfig

        cfg = SiteConfig(title="T", url=HttpUrl("https://x.com"), author="A")
        assert cfg.navigation.items == []

    def test_navigation_can_be_set(self, tmp_path: Path) -> None:
        from github_blog.config import Settings

        yaml = """
github:
  repo: u/r
  allowed_authors: [u]
site:
  title: T
  url: https://x.com
  author: A
  navigation:
    items:
      - name: Blog
        url: /blog/
about:
  issue_number: 1
security:
  token_env: G_T
"""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(yaml)
        settings = Settings.load_from_yaml(yaml_file)
        assert len(settings.site.navigation.items) == 1
        assert settings.site.navigation.items[0].name == "Blog"


# ---------------------------------------------------------------------------
# Canonical HTTPS origin
# ---------------------------------------------------------------------------


class TestCanonicalHttps:
    def test_http_url_rejected(self, tmp_path: Path) -> None:
        yaml = """
github:
  repo: u/r
  allowed_authors: [u]
site:
  title: T
  url: http://example.com
  author: A
about:
  issue_number: 1
security:
  token_env: G_T
"""
        with pytest.raises(ValidationError, match="HTTPS"):
            _load_settings(yaml, tmp_path)

    def test_https_url_accepted(self, tmp_path: Path) -> None:
        settings = _load_settings(_base_yaml(), tmp_path)
        assert settings.site.url.scheme == "https"


# ---------------------------------------------------------------------------
# Site Profile
# ---------------------------------------------------------------------------


class TestSiteProfile:
    def test_avatar_bio_links(self, tmp_path: Path) -> None:
        settings = _load_settings(_base_yaml(), tmp_path)
        assert settings.profile.avatar == "https://github.com/geoqiao.png"
        assert settings.profile.bio == "Test bio"
        assert len(settings.profile.links) == 1

    def test_no_expertise_field(self, tmp_path: Path) -> None:
        """Site Profile contains only avatar, bio, links - no expertise."""
        yaml = _base_yaml().replace(
            "  bio: Test bio\n", "  bio: Test bio\n  expertise: [x]\n", 1
        )
        with pytest.raises(ValidationError, match="expertise"):
            _load_settings(yaml, tmp_path)

    def test_profile_all_optional(self, tmp_path: Path) -> None:
        from github_blog.config import SiteProfileConfig

        cfg = SiteProfileConfig()
        assert cfg.avatar == ""
        assert cfg.bio == ""
        assert cfg.links == []


# ---------------------------------------------------------------------------
# AboutConfig - immutable Issue selection
# ---------------------------------------------------------------------------


class TestAboutConfig:
    def test_issue_number_required(self, tmp_path: Path) -> None:
        yaml = """
github:
  repo: u/r
  allowed_authors: [u]
site:
  title: T
  url: https://x.com
  author: A
about: {}
security:
  token_env: G_T
"""
        with pytest.raises(ValidationError, match="issue_number"):
            _load_settings(yaml, tmp_path)

    def test_issue_number_positive(self) -> None:
        from github_blog.config import AboutConfig

        cfg = AboutConfig(issue_number=1)
        assert cfg.issue_number == 1

    def test_issue_number_zero_rejected(self) -> None:
        from github_blog.config import AboutConfig

        with pytest.raises(ValidationError):
            AboutConfig(issue_number=0)

    def test_issue_number_negative_rejected(self) -> None:
        from github_blog.config import AboutConfig

        with pytest.raises(ValidationError):
            AboutConfig(issue_number=-1)


# ---------------------------------------------------------------------------
# PathsConfig - positive page size, default 10
# ---------------------------------------------------------------------------


class TestPathsConfig:
    def test_page_size_default_10(self) -> None:
        from github_blog.config import PathsConfig

        cfg = PathsConfig()
        assert cfg.page_size == 10

    def test_page_size_positive(self) -> None:
        from github_blog.config import PathsConfig

        cfg = PathsConfig(page_size=20)
        assert cfg.page_size == 20

    def test_page_size_zero_rejected(self) -> None:
        from github_blog.config import PathsConfig

        with pytest.raises(ValidationError):
            PathsConfig(page_size=0)

    def test_page_size_negative_rejected(self) -> None:
        from github_blog.config import PathsConfig

        with pytest.raises(ValidationError):
            PathsConfig(page_size=-5)

    def test_home_post_count_not_configurable(self) -> None:
        """Home recent Blog count is fixed at 5 for v1 - not in paths config."""
        from github_blog.config import PathsConfig

        with pytest.raises(ValidationError, match="home_post_count"):
            PathsConfig(home_post_count=5)  # type: ignore

    def test_no_language_in_paths(self) -> None:
        """Language moved to site identity, not paths."""
        from github_blog.config import PathsConfig

        with pytest.raises(ValidationError, match="language"):
            PathsConfig(language="en")  # type: ignore

    def test_theme_path_property(self) -> None:
        from github_blog.config import PathsConfig

        cfg = PathsConfig(theme="Escape2")
        assert cfg.theme_path == Path("templates/Escape2")

    def test_output_default(self) -> None:
        from github_blog.config import PathsConfig

        cfg = PathsConfig()
        assert cfg.output == "output"


# ---------------------------------------------------------------------------
# CommentsConfig
# ---------------------------------------------------------------------------


class TestCommentsConfig:
    def test_defaults(self) -> None:
        from github_blog.config import CommentsConfig

        cfg = CommentsConfig()
        assert cfg.provider == "utterances"
        assert cfg.repo == ""
        assert cfg.theme == "github-light"
        assert cfg.theme_mode == "auto"

    def test_all_fields_set(self) -> None:
        from github_blog.config import CommentsConfig

        cfg = CommentsConfig(
            provider="utterances",
            repo="user/repo",
            theme="github-dark",
            theme_mode="auto",
        )
        assert cfg.repo == "user/repo"
        assert cfg.theme == "github-dark"


# ---------------------------------------------------------------------------
# SecurityConfig - dynamic token env, no hardcoded default
# ---------------------------------------------------------------------------


class TestSecurityConfig:
    def test_token_env_required(self) -> None:
        from github_blog.config import SecurityConfig

        with pytest.raises(ValidationError):
            SecurityConfig()  # type: ignore

    def test_token_env_can_be_customized(self) -> None:
        from github_blog.config import SecurityConfig

        cfg = SecurityConfig(token_env="MY_TOKEN")  # noqa: S106
        assert cfg.token_env == "MY_TOKEN"  # noqa: S105

    def test_no_hardcoded_constant(self) -> None:
        """The module must not export a hard-coded TOKEN_ENV_VAR constant."""
        import github_blog.config as config_mod

        assert not hasattr(config_mod, "TOKEN_ENV_VAR"), (
            "config module must not hard-code a TOKEN_ENV_VAR constant"
        )


# ---------------------------------------------------------------------------
# Project catalog entries
# ---------------------------------------------------------------------------


class TestProjectCatalog:
    def test_required_fields(self) -> None:
        from github_blog.config import ProjectCatalogEntry

        entry = ProjectCatalogEntry(
            slug="my-project",
            title="My Project",
            repository="user/repo",
            summary="A great project",
        )
        assert entry.slug == "my-project"
        assert entry.featured is False
        assert entry.order == 0

    def test_optional_fields(self) -> None:
        from github_blog.config import ProjectCatalogEntry

        entry = ProjectCatalogEntry(
            slug="p",
            title="P",
            repository="r",
            summary="s",
            featured=True,
            order=2,
        )
        assert entry.featured is True
        assert entry.order == 2

    def test_fallback_metadata(self) -> None:
        from github_blog.config import ProjectCatalogEntry, ProjectFallbackMetadata

        entry = ProjectCatalogEntry(
            slug="p",
            title="P",
            repository="r",
            summary="s",
            fallback_metadata=ProjectFallbackMetadata(
                stars=100,
                forks=10,
                language="Python",
                topics=["web"],
            ),
        )
        assert entry.fallback_metadata is not None
        assert entry.fallback_metadata.stars == 100
        assert entry.fallback_metadata.language == "Python"

    def test_fallback_stars_negative_rejected(self) -> None:
        from github_blog.config import ProjectFallbackMetadata

        with pytest.raises(ValidationError):
            ProjectFallbackMetadata(stars=-1)

    def test_fallback_forks_negative_rejected(self) -> None:
        from github_blog.config import ProjectFallbackMetadata

        with pytest.raises(ValidationError):
            ProjectFallbackMetadata(forks=-1)

    def test_projects_optional_in_settings(self, tmp_path: Path) -> None:
        settings = _load_settings(_base_yaml(), tmp_path)
        assert settings.projects == []


# ---------------------------------------------------------------------------
# Theme lock
# ---------------------------------------------------------------------------


class TestThemeLock:
    def test_required_fields(self) -> None:
        from github_blog.config import ThemeLockConfig

        lock = ThemeLockConfig(
            repository="org/theme",
            commit="a" * 40,
            api_version="1",
        )
        assert lock.repository == "org/theme"
        assert lock.api_version == "1"

    def test_commit_must_be_full_sha(self) -> None:
        from github_blog.config import ThemeLockConfig

        with pytest.raises(ValidationError, match="40-character"):
            ThemeLockConfig(repository="r", commit="abc123", api_version="1")

    def test_commit_hex_only(self) -> None:
        from github_blog.config import ThemeLockConfig

        with pytest.raises(ValidationError):
            ThemeLockConfig(
                repository="r",
                commit="g" * 40,
                api_version="1",
            )

    def test_theme_lock_optional_in_settings(self, tmp_path: Path) -> None:
        settings = _load_settings(_base_yaml(), tmp_path)
        assert settings.theme_lock is None


# ---------------------------------------------------------------------------
# Settings integration
# ---------------------------------------------------------------------------


class TestSettings:
    def test_load_from_yaml(self, tmp_path: Path) -> None:
        settings = _load_settings(_base_yaml(), tmp_path)
        assert settings.site.title == "Test Blog"
        assert settings.github.repo == "geoqiao/geoqiao.github.io"
        assert settings.about.issue_number == 42
        assert settings.security.token_env == "G_T"  # noqa: S105

    def test_all_sections_present(self, tmp_path: Path) -> None:
        settings = _load_settings(_base_yaml(), tmp_path)
        assert hasattr(settings, "github")
        assert hasattr(settings, "site")
        assert hasattr(settings, "profile")
        assert hasattr(settings, "about")
        assert hasattr(settings, "branding")
        assert hasattr(settings, "paths")
        assert hasattr(settings, "seo")
        assert hasattr(settings, "comments")
        assert hasattr(settings, "security")
        assert hasattr(settings, "projects")
        assert hasattr(settings, "theme_lock")

    def test_extra_top_level_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            _load_settings(_base_yaml() + "stray: 1\n", tmp_path)

    def test_comments_repo_fallback(self, tmp_path: Path) -> None:
        """When comments.repo is empty, consumers fall back to github.repo."""
        settings = _load_settings(_base_yaml(), tmp_path)
        assert settings.comments.repo == ""
        # The fallback happens in render_service, not in the config model;
        # here we just verify the empty default.
        fallback = settings.comments.repo or settings.github.repo
        assert fallback == "geoqiao/geoqiao.github.io"


# ---------------------------------------------------------------------------
# Canonical HTTPS origin - strict origin validation
# ---------------------------------------------------------------------------


class TestCanonicalOrigin:
    """The canonical origin must be a true HTTPS origin.

    No userinfo, non-root path, query, or fragment is allowed.  Only the
    root-slash form is accepted (and normalized when the slash is omitted).
    """

    def test_accepts_root_slash(self, tmp_path: Path) -> None:
        settings = _load_settings(_base_yaml(), tmp_path)
        assert str(settings.site.url) == "https://example.com/"

    def test_normalizes_no_slash_to_root_slash(self, tmp_path: Path) -> None:
        yaml = _base_yaml().replace(
            "  url: https://example.com\n", "  url: https://example.com\n", 1
        )
        settings = _load_settings(yaml, tmp_path)
        assert str(settings.site.url) == "https://example.com/"

    def test_rejects_userinfo(self, tmp_path: Path) -> None:
        yaml = _base_yaml().replace(
            "  url: https://example.com\n",
            "  url: https://user:pass@example.com/\n",
            1,
        )
        with pytest.raises(ValidationError, match="userinfo"):
            _load_settings(yaml, tmp_path)

    def test_rejects_non_root_path(self, tmp_path: Path) -> None:
        yaml = _base_yaml().replace(
            "  url: https://example.com\n",
            "  url: https://example.com/blog\n",
            1,
        )
        with pytest.raises(ValidationError, match="root path"):
            _load_settings(yaml, tmp_path)

    def test_rejects_query(self, tmp_path: Path) -> None:
        yaml = _base_yaml().replace(
            "  url: https://example.com\n",
            "  url: https://example.com/?q=1\n",
            1,
        )
        with pytest.raises(ValidationError, match="query"):
            _load_settings(yaml, tmp_path)

    def test_rejects_fragment(self, tmp_path: Path) -> None:
        yaml = _base_yaml().replace(
            "  url: https://example.com\n",
            "  url: https://example.com/#frag\n",
            1,
        )
        with pytest.raises(ValidationError, match="fragment"):
            _load_settings(yaml, tmp_path)

    def test_rejects_path_params(self, tmp_path: Path) -> None:
        """URL params (``;`` segment params) must be rejected, not normalized."""
        yaml = _base_yaml().replace(
            "  url: https://example.com\n",
            "  url: https://example.com/;foo\n",
            1,
        )
        with pytest.raises(ValidationError, match="path parameter"):
            _load_settings(yaml, tmp_path)

    def test_rejects_http(self, tmp_path: Path) -> None:
        yaml = """
github:
  repo: u/r
  allowed_authors: [u]
site:
  title: T
  url: http://example.com/
  author: A
about:
  issue_number: 1
security:
  token_env: G_T
"""
        with pytest.raises(ValidationError, match="HTTPS"):
            _load_settings(yaml, tmp_path)


# ---------------------------------------------------------------------------
# Strengthened value semantics
# ---------------------------------------------------------------------------


class TestRepoValueSemantics:
    """GitHub repo must be exactly 'owner/repo' with nonempty components."""

    def test_rejects_no_slash(self) -> None:
        from github_blog.config import GithubConfig

        with pytest.raises(ValidationError, match="owner/repo"):
            GithubConfig(repo="invalid-no-slash", allowed_authors=["user"])

    def test_rejects_empty_owner(self) -> None:
        from github_blog.config import GithubConfig

        with pytest.raises(ValidationError, match="owner"):
            GithubConfig(repo="/repo", allowed_authors=["user"])

    def test_rejects_empty_repo(self) -> None:
        from github_blog.config import GithubConfig

        with pytest.raises(ValidationError, match="repo"):
            GithubConfig(repo="user/", allowed_authors=["user"])

    def test_rejects_multiple_slashes(self) -> None:
        from github_blog.config import GithubConfig

        with pytest.raises(ValidationError, match="owner/repo"):
            GithubConfig(repo="user/repo/extra", allowed_authors=["user"])

    def test_rejects_whitespace_owner(self) -> None:
        from github_blog.config import GithubConfig

        with pytest.raises(ValidationError, match="owner"):
            GithubConfig(repo=" /repo", allowed_authors=["user"])

    def test_rejects_whitespace_repo(self) -> None:
        from github_blog.config import GithubConfig

        with pytest.raises(ValidationError, match="repo"):
            GithubConfig(repo="user/ ", allowed_authors=["user"])

    def test_accepts_valid(self) -> None:
        from github_blog.config import GithubConfig

        cfg = GithubConfig(repo="geoqiao/blog", allowed_authors=["geoqiao"])
        assert cfg.repo == "geoqiao/blog"
        assert cfg.username == "geoqiao"


class TestAllowedAuthorsSemantics:
    """Allowed authors must be nonblank; duplicates are rejected."""

    def test_rejects_blank_author(self, tmp_path: Path) -> None:
        yaml = _base_yaml().replace("    - geoqiao\n", "    - geoqiao\n    - ''\n", 1)
        with pytest.raises(ValidationError, match="blank"):
            _load_settings(yaml, tmp_path)

    def test_rejects_whitespace_only_author(self, tmp_path: Path) -> None:
        yaml = _base_yaml().replace(
            "    - geoqiao\n", "    - geoqiao\n    - '   '\n", 1
        )
        with pytest.raises(ValidationError, match="blank"):
            _load_settings(yaml, tmp_path)

    def test_rejects_duplicate_authors(self, tmp_path: Path) -> None:
        yaml = _base_yaml().replace(
            "    - geoqiao\n", "    - geoqiao\n    - geoqiao\n", 1
        )
        with pytest.raises(ValidationError, match="duplicate"):
            _load_settings(yaml, tmp_path)

    def test_rejects_duplicate_authors_case_insensitive(self, tmp_path: Path) -> None:
        yaml = _base_yaml().replace(
            "    - geoqiao\n", "    - geoqiao\n    - Geoqiao\n", 1
        )
        with pytest.raises(ValidationError, match="duplicate"):
            _load_settings(yaml, tmp_path)

    def test_accepts_distinct_authors(self, tmp_path: Path) -> None:
        yaml = _base_yaml().replace(
            "    - geoqiao\n", "    - geoqiao\n    - alice\n", 1
        )
        settings = _load_settings(yaml, tmp_path)
        assert settings.github.allowed_authors == ["geoqiao", "alice"]


class TestTokenEnvSemantics:
    """Security token env must be a valid nonblank environment variable identifier."""

    def test_rejects_empty(self) -> None:
        from github_blog.config import SecurityConfig

        with pytest.raises(ValidationError, match="blank"):
            SecurityConfig(token_env="")

    def test_rejects_whitespace_only(self) -> None:
        from github_blog.config import SecurityConfig

        with pytest.raises(ValidationError, match="blank"):
            SecurityConfig(token_env="   ")  # noqa: S106

    def test_rejects_starting_with_digit(self) -> None:
        from github_blog.config import SecurityConfig

        with pytest.raises(ValidationError, match="identifier"):
            SecurityConfig(token_env="1ABC")  # noqa: S106

    def test_rejects_hyphen(self) -> None:
        from github_blog.config import SecurityConfig

        with pytest.raises(ValidationError, match="identifier"):
            SecurityConfig(token_env="G-T")  # noqa: S106

    def test_rejects_special_chars(self) -> None:
        from github_blog.config import SecurityConfig

        with pytest.raises(ValidationError, match="identifier"):
            SecurityConfig(token_env="TOKEN!")  # noqa: S106

    def test_accepts_valid_identifier(self) -> None:
        from github_blog.config import SecurityConfig

        cfg = SecurityConfig(token_env="G_T")  # noqa: S106
        assert cfg.token_env == "G_T"  # noqa: S105

    def test_accepts_underscore_prefix(self) -> None:
        from github_blog.config import SecurityConfig

        cfg = SecurityConfig(token_env="_TOKEN")  # noqa: S106
        assert cfg.token_env == "_TOKEN"  # noqa: S105

    def test_accepts_alphanumeric_underscore(self) -> None:
        from github_blog.config import SecurityConfig

        cfg = SecurityConfig(token_env="MY_TOKEN_123")  # noqa: S106
        assert cfg.token_env == "MY_TOKEN_123"  # noqa: S105


class TestChildPathValidation:
    """Legacy child path/name fields must be safe single names/filenames."""

    def test_rejects_absolute_theme(self) -> None:
        from github_blog.config import PathsConfig

        with pytest.raises(ValidationError, match="absolute"):
            PathsConfig(theme="/etc")

    def test_rejects_separator_in_blog(self) -> None:
        from github_blog.config import PathsConfig

        with pytest.raises(ValidationError, match="separator"):
            PathsConfig(blog="foo/bar")

    def test_rejects_dot_in_tag(self) -> None:
        from github_blog.config import PathsConfig

        with pytest.raises(ValidationError, match=r"'\.'|dot"):
            PathsConfig(tag=".")

    def test_rejects_dotdot_in_page(self) -> None:
        from github_blog.config import PathsConfig

        with pytest.raises(ValidationError, match=r"\.\.|dot"):
            PathsConfig(page="..")

    def test_rejects_dotdot_in_rss(self) -> None:
        from github_blog.config import PathsConfig

        with pytest.raises(ValidationError, match="separator"):
            PathsConfig(rss="../evil")

    def test_rejects_dotdot_in_about(self) -> None:
        from github_blog.config import PathsConfig

        with pytest.raises(ValidationError, match="separator"):
            PathsConfig(about="../evil")

    def test_rejects_separator_in_page(self) -> None:
        from github_blog.config import PathsConfig

        with pytest.raises(ValidationError, match="separator"):
            PathsConfig(page="foo/bar")

    def test_accepts_valid_defaults(self) -> None:
        from github_blog.config import PathsConfig

        cfg = PathsConfig()
        assert cfg.theme == "Escape1"
        assert cfg.blog == "blog"
        assert cfg.tag == "tag"
        assert cfg.page == "page"
        assert cfg.rss == "atom.xml"
        assert cfg.about == "about.html"

    def test_accepts_valid_custom_names(self) -> None:
        from github_blog.config import PathsConfig

        cfg = PathsConfig(
            theme="Escape2",
            blog="posts",
            tag="topics",
            page="p",
            rss="feed.xml",
            about="me.html",
        )
        assert cfg.theme == "Escape2"
        assert cfg.blog == "posts"
        assert cfg.rss == "feed.xml"
