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
- ``theme``: explicit built-in package resource or Config-relative local source.
- ``comments``: Utterances repository fallback, theme, and ``theme_mode``.
- ``security``: dynamic token environment-variable name (no hard-coded default).
- ``projects``: repository-owned project catalog entries with strict fields.
- ``seo`` / ``branding``: active verification and attribution fields only.

Settings are explicitly injected into compiler and rendering collaborators.
No global settings singleton is introduced.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Literal
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
_REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]+$")
_UTTERANCES_THEMES = frozenset(
    {
        "boxy-light",
        "dark-blue",
        "github-dark",
        "github-dark-orange",
        "github-light",
        "gruvbox-dark",
        "icy-dark",
        "photon-dark",
        "preferred-color-scheme",
    }
)


def _validate_repository(value: str) -> str:
    if not _REPOSITORY_PATTERN.fullmatch(value):
        raise ValueError("repository must be in valid 'owner/repo' format")
    return value


def _validate_safe_href(value: str) -> str:
    if (
        not value
        or "\\" in value
        or any(
            char.isspace() or ord(char) < 32 or 0x7F <= ord(char) <= 0x9F
            for char in value
        )
    ):
        raise ValueError("link URL contains whitespace, a backslash, or control data")

    if value.startswith("#"):
        if len(value) == 1:
            raise ValueError("link fragment must not be empty")
        return value

    parsed = urlparse(value)
    if value.startswith("/"):
        if value.startswith("//") or parsed.scheme or parsed.netloc:
            raise ValueError("protocol-relative links are not allowed")
        return value

    if parsed.scheme == "https" and parsed.hostname:
        if parsed.username or parsed.password:
            raise ValueError("HTTPS links must not contain userinfo")
        return value

    if parsed.scheme == "mailto" and parsed.path and not parsed.netloc:
        return value

    raise ValueError("link URL must be HTTPS, mailto, root-relative, or a fragment")


def _validate_safe_resource_url(value: str) -> str:
    if not value:
        return value
    validated = _validate_safe_href(value)
    if validated.startswith("#") or urlparse(validated).scheme == "mailto":
        raise ValueError("resource URL must be HTTPS or root-relative")
    return validated


class GithubConfig(BaseModel):
    """GitHub repository and content-selection configuration."""

    model_config = ConfigDict(extra="forbid")

    repo: str
    allowed_authors: list[str] = Field(min_length=1)

    @field_validator("repo")
    @classmethod
    def validate_repo(cls, v: str) -> str:
        return _validate_repository(v)

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


class Link(BaseModel):
    """A named link whose rendered destination cannot execute script."""

    model_config = ConfigDict(extra="forbid")

    name: str
    url: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("link name must not be empty or blank")
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _validate_safe_href(v)


class NavigationConfig(BaseModel):
    """Site navigation configuration."""

    model_config = ConfigDict(extra="forbid")

    items: list[Link] = Field(default_factory=list)


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


class SiteProfileConfig(BaseModel):
    """Site Profile — avatar, short bio, and links only.

    The detailed About narrative belongs to About Issue Content, not this
    section.
    """

    model_config = ConfigDict(extra="forbid")

    avatar: str = ""
    bio: str = ""
    links: list[Link] = Field(default_factory=list)

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, v: str) -> str:
        return _validate_safe_resource_url(v)


class AboutConfig(BaseModel):
    """About Issue selection — immutable by configured Issue number."""

    model_config = ConfigDict(extra="forbid")

    issue_number: int = Field(gt=0)


class PathsConfig(BaseModel):
    """Strict output and pagination configuration."""

    model_config = ConfigDict(extra="forbid")

    output: str = "output"
    page_size: int = Field(default=10, gt=0)


class BuiltinThemeConfig(BaseModel):
    """A reference Theme shipped as a generator package resource."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["builtin"] = "builtin"
    name: str = "geoqiao.me"

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return validate_output_child_name(v, "theme name")


class LocalThemeConfig(BaseModel):
    """A site-owned Theme directory relative to the Config root."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["local"] = "local"
    name: str
    path: Path

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return validate_output_child_name(v, "theme name")

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: Path) -> Path:
        if v.is_absolute() or not v.parts or ".." in v.parts:
            raise ValueError("local theme path must stay relative to the Config root")
        return v


ThemeConfig = Annotated[
    BuiltinThemeConfig | LocalThemeConfig, Field(discriminator="source")
]


class CommentsConfig(BaseModel):
    """Utterances comments configuration.

    ``repo`` falls back to ``github.repo`` when empty.  ``theme_mode: auto``
    follows the blog theme via postMessage / MutationObserver.
    """

    model_config = ConfigDict(extra="forbid")

    repo: str = ""
    theme: str = "github-light"
    theme_mode: Literal["auto", "fixed"] = "auto"

    @field_validator("repo")
    @classmethod
    def validate_repo(cls, v: str) -> str:
        return _validate_repository(v) if v else v

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, v: str) -> str:
        if v not in _UTTERANCES_THEMES:
            raise ValueError("unsupported Utterances theme")
        return v


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


class BrandingConfig(BaseModel):
    """Branding and footer configuration."""

    model_config = ConfigDict(extra="forbid")

    show_powered_by: bool = True
    powered_by_text: str = "Powered by"
    powered_by_url: str = "https://github.com/geoqiao/escaping"
    source_link_url: str = ""

    @field_validator("powered_by_url", "source_link_url")
    @classmethod
    def validate_link_url(cls, v: str) -> str:
        return _validate_safe_href(v) if v else v


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

    @field_validator("repository")
    @classmethod
    def validate_repository(cls, v: str) -> str:
        return _validate_repository(v)


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
    theme: ThemeConfig = Field(default_factory=BuiltinThemeConfig)
    seo: SeoConfig = Field(default_factory=SeoConfig)
    comments: CommentsConfig = Field(default_factory=CommentsConfig)
    security: SecurityConfig
    projects: list[ProjectCatalogEntry] = Field(default_factory=list)

    @classmethod
    def load_from_yaml(cls, yaml_path: Path) -> Settings:
        """Load settings from a YAML file."""
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)
