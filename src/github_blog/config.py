"""Strict Pydantic configuration models for the Site Compiler.

All models reject unknown fields (``extra="forbid"``) so that misspelled or
unrecognized settings fail loudly instead of being silently ignored.

Configuration contract (per accepted spec):
- ``github``: repository identity and a non-empty ``allowed_authors`` list.
- ``site``: top-level site identity — title, author/display name, canonical
  HTTPS origin, description, language, and navigation.
- ``profile``: Site Profile — avatar, short bio, and links only.
- ``about``: immutable About Issue selection by ``issue_number``.
- ``paths``: output and page-size configuration (positive, default 10).
- ``comments``: provider, repository fallback, theme, and ``theme_mode``.
- ``security``: dynamic token environment-variable name (no hard-coded default).
- ``projects``: repository-owned project catalog entries with strict fields.
- ``theme_lock``: optional immutable theme reference (repository, commit, API
  version).
- ``seo`` / ``branding``: preserved existing sections, now strict.

Settings are explicitly injected into compiler and rendering collaborators.
No global settings singleton is introduced.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
)

from .output_safety import validate_output_child_name

#: Valid POSIX shell environment-variable identifier pattern.
_ENV_VAR_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class GithubConfig(BaseModel):
    """GitHub repository and content-selection configuration."""

    model_config = ConfigDict(extra="forbid")

    repo: str
    allowed_authors: list[str] = Field(min_length=1)

    @field_validator("repo")
    @classmethod
    def validate_repo(cls, v: str) -> str:
        parts = v.split("/")
        if len(parts) != 2:
            raise ValueError("repo must be in 'owner/repo' format")
        owner, repo_name = parts
        if not owner.strip():
            raise ValueError("repo owner must not be empty or blank")
        if not repo_name.strip():
            raise ValueError("repo name must not be empty or blank")
        return v

    @field_validator("allowed_authors")
    @classmethod
    def validate_allowed_authors(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        for author in v:
            if not author.strip():
                raise ValueError("allowed_authors must not contain blank entries")
            key = author.strip().casefold()
            if key in seen:
                raise ValueError(f"duplicate allowed_author: {author!r}")
            seen.add(key)
        return v

    @property
    def username(self) -> str:
        """Derive username from the ``repo`` field (``user/repo``)."""
        if "/" in self.repo:
            return self.repo.split("/")[0]
        return self.repo


class NavigationLink(BaseModel):
    """A single navigation link."""

    model_config = ConfigDict(extra="forbid")

    name: str
    url: str


class NavigationConfig(BaseModel):
    """Site navigation configuration."""

    model_config = ConfigDict(extra="forbid")

    items: list[NavigationLink] = Field(default_factory=list)


class SiteConfig(BaseModel):
    """Top-level site identity.

    Owns display name, canonical HTTPS origin, description, language, and
    navigation.  The canonical origin must use HTTPS.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    author: str
    url: HttpUrl
    description: str = ""
    language: str = "en"
    navigation: NavigationConfig = Field(default_factory=NavigationConfig)

    @field_validator("url", mode="before")
    @classmethod
    def validate_canonical_origin(cls, v: str | HttpUrl) -> str:
        """Validate that the canonical origin is a true HTTPS origin.

        No userinfo, non-root path, query, or fragment is allowed.  The
        root-slash form is normalized when the trailing slash is omitted.
        """
        if isinstance(v, HttpUrl):
            v = str(v)

        parsed = urlparse(v)
        if parsed.scheme != "https":
            raise ValueError("canonical origin must use HTTPS")
        if parsed.username or parsed.password:
            raise ValueError("canonical origin must not contain userinfo")
        if parsed.path not in ("", "/"):
            raise ValueError(
                "canonical origin must be a root path only (no non-root path)"
            )
        if parsed.query:
            raise ValueError("canonical origin must not contain a query string")
        if parsed.fragment:
            raise ValueError("canonical origin must not contain a fragment")
        if parsed.params:
            raise ValueError("canonical origin must not contain path parameters")

        # Normalize to root-slash form.
        return urlunparse(("https", parsed.netloc, "/", "", "", ""))


class ProfileLink(BaseModel):
    """A link in the Site Profile."""

    model_config = ConfigDict(extra="forbid")

    name: str
    url: str


class SiteProfileConfig(BaseModel):
    """Site Profile — avatar, short bio, and links only.

    The detailed About narrative belongs to About Issue Content, not this
    section.
    """

    model_config = ConfigDict(extra="forbid")

    avatar: str = ""
    bio: str = ""
    links: list[ProfileLink] = Field(default_factory=list)


class AboutConfig(BaseModel):
    """About Issue selection — immutable by configured Issue number."""

    model_config = ConfigDict(extra="forbid")

    issue_number: int = Field(gt=0)


class PathsConfig(BaseModel):
    """Strict output, theme, and pagination configuration."""

    model_config = ConfigDict(extra="forbid")

    output: str = "output"
    theme: str = "geoqiao.me"
    page_size: int = Field(default=10, gt=0)

    @field_validator("theme")
    @classmethod
    def validate_theme_name(cls, v: str) -> str:
        return validate_output_child_name(v, "theme")

    @property
    def theme_path(self) -> Path:
        return Path("templates") / self.theme

    @property
    def theme_url_path(self) -> str:
        return f"/templates/{self.theme}"


class CommentsConfig(BaseModel):
    """Comments provider configuration.

    ``repo`` falls back to ``github.repo`` when empty.  ``theme_mode: auto``
    follows the blog theme via postMessage / MutationObserver.
    """

    model_config = ConfigDict(extra="forbid")

    provider: str = "utterances"
    repo: str = ""
    theme: str = "github-light"
    theme_mode: str = "auto"


class SecurityConfig(BaseModel):
    """Security settings - the token environment-variable name.

    The variable name is selected by configuration; no hard-coded default
    exists so that callers must be explicit.
    """

    model_config = ConfigDict(extra="forbid")

    token_env: str

    @field_validator("token_env")
    @classmethod
    def validate_token_env(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("token_env must not be empty or blank")
        if not _ENV_VAR_PATTERN.match(v):
            raise ValueError(
                "token_env must be a valid environment variable identifier "
                "(start with a letter or underscore; contain only letters, "
                "digits, and underscores)"
            )
        return v


class SeoConfig(BaseModel):
    """SEO configuration."""

    model_config = ConfigDict(extra="forbid")

    google_search_console: str = ""
    enable_sitemap: bool = True
    enable_robots: bool = True


class BrandingConfig(BaseModel):
    """Branding and footer configuration."""

    model_config = ConfigDict(extra="forbid")

    show_powered_by: bool = True
    powered_by_text: str = "Powered by"
    powered_by_url: str = "https://github.com/geoqiao/github-blog"
    show_intro: bool = False
    intro_text: str = ""
    intro_text2: str = "Generated with Python + Jinja2, deployed via GitHub Actions."
    source_link_text: str = "View Source"
    source_link_url: str = ""


class ProjectFallbackMetadata(BaseModel):
    """Optional fallback metadata for a project catalog entry.

    Used when GitHub API enrichment fails.  ``stars`` and ``forks`` must be
    non-negative.
    """

    model_config = ConfigDict(extra="forbid")

    stars: int | None = Field(default=None, ge=0)
    forks: int | None = Field(default=None, ge=0)
    language: str | None = None
    topics: list[str] | None = None


class ProjectCatalogEntry(BaseModel):
    """A curated project catalog entry — repository-owned, not Issue-authored.

    Each entry requires ``slug``, ``title``, ``repository``, and ``summary``,
    and supports ``featured`` plus numeric ``order``.  Entries sort
    deterministically by ``order`` then ``slug``.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str
    title: str
    repository: str
    summary: str
    featured: bool = False
    order: int = 0
    fallback_metadata: ProjectFallbackMetadata | None = None


class ThemeLockConfig(BaseModel):
    """Immutable theme reference — repository, full commit, and API version.

    Theme builds resolve site overrides before the locked theme.  Upgrades
    happen only through an explicit theme update operation.
    """

    model_config = ConfigDict(extra="forbid")

    repository: str
    commit: str
    api_version: str

    @field_validator("commit")
    @classmethod
    def validate_full_commit(cls, v: str) -> str:
        if len(v) != 40 or not all(c in "0123456789abcdef" for c in v.lower()):
            raise ValueError("commit must be a full 40-character hex SHA")
        return v


class Settings(BaseModel):
    """Application settings composing all configuration sections.

    All sections reject unknown fields.  Settings are explicitly injected into
    compiler and rendering collaborators; no global singleton is introduced.
    """

    model_config = ConfigDict(extra="forbid")

    github: GithubConfig
    site: SiteConfig
    profile: SiteProfileConfig = Field(default_factory=SiteProfileConfig)
    about: AboutConfig
    branding: BrandingConfig = Field(default_factory=BrandingConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    seo: SeoConfig = Field(default_factory=SeoConfig)
    comments: CommentsConfig = Field(default_factory=CommentsConfig)
    security: SecurityConfig
    projects: list[ProjectCatalogEntry] = Field(default_factory=list)
    theme_lock: ThemeLockConfig | None = None

    @classmethod
    def load_from_yaml(cls, yaml_path: Path) -> Settings:
        """Load settings from a YAML file."""
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)
