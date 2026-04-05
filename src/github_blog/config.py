"""Pydantic configuration models for github-blog.

This module defines 8 independent configuration sections:
- GithubConfig: GitHub repository settings
- BlogConfig: Blog metadata
- AboutConfig: About page content
- BrandingConfig: Branding and footer settings
- PathsConfig: File paths and URL configuration
- SeoConfig: SEO settings
- CommentsConfig: Comments provider settings
- SecurityConfig: Security settings
"""

import logging
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, HttpUrl
from pydantic_settings import SettingsConfigDict

logger = logging.getLogger(__name__)


class GithubConfig(BaseModel):
    """GitHub repository configuration."""

    repo: str
    _username: Optional[str] = None

    @property
    def username(self) -> str:
        """Resolve username from repo if not explicitly set."""
        if self._username is not None:
            return self._username
        if "/" in self.repo:
            return self.repo.split("/")[0]
        return self.repo

    def resolve_username(self) -> str:
        """Resolve username (alias for username property)."""
        return self.username


class BlogConfig(BaseModel):
    """Blog metadata configuration."""

    title: str
    url: HttpUrl
    author: str


class AboutLink(BaseModel):
    """Link in the about section."""

    name: str
    url: str


class AboutConfig(BaseModel):
    """About page configuration."""

    avatar: str = ""
    bio: str
    expertise: list[str] = Field(default_factory=list)
    links: list[AboutLink] = Field(default_factory=list)


class BrandingConfig(BaseModel):
    """Branding and footer configuration."""

    show_powered_by: bool = True
    powered_by_text: str = "Powered by"
    powered_by_url: str = "https://github.com/geoqiao/github-blog"
    show_intro: bool = False
    intro_text: str = ""
    source_link_text: str = "View Source"
    source_link_url: str = ""


class PathsConfig(BaseModel):
    """File paths and URL configuration."""

    output: str = "output"
    theme: str = "BearMinimal"
    blog: str = "blog"
    tag: str = "tag"
    rss: str = "atom.xml"
    about: str = "about.html"
    page_size: int = 10
    home_post_count: int = 10
    language: str = "en"

    @property
    def theme_path(self) -> Path:
        """Return Path to theme directory."""
        return Path("templates") / self.theme

    @property
    def seo_path(self) -> Path:
        """Return Path to SEO templates."""
        return Path("templates/seo")

    @property
    def theme_url_path(self) -> str:
        """Return URL path for theme assets."""
        return f"/templates/{self.theme}"


class SeoConfig(BaseModel):
    """SEO configuration."""

    google_search_console: str = ""
    enable_sitemap: bool = True
    enable_robots: bool = True


class CommentsConfig(BaseModel):
    """Comments provider configuration."""

    provider: str = "utterances"
    repo: str = ""
    theme: str = "github-light"


class SecurityConfig(BaseModel):
    """Security settings."""

    token_env: str = "G_T"


class Settings(BaseModel):
    """Application settings composing all 8 config sections."""

    github: GithubConfig
    blog: BlogConfig
    about: AboutConfig
    branding: BrandingConfig = Field(default_factory=BrandingConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    seo: SeoConfig = Field(default_factory=SeoConfig)
    comments: CommentsConfig = Field(default_factory=CommentsConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    model_config = SettingsConfigDict(extra="ignore")

    @classmethod
    def load_from_yaml(cls, yaml_path: Path) -> "Settings":
        """Load settings from a YAML file."""
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance.

    Returns:
        The global Settings instance.

    Raises:
        RuntimeError: If settings have not been loaded.
    """
    global _settings
    if _settings is None:
        load_settings()
    assert _settings is not None
    return _settings


def load_settings() -> Settings:
    """Load settings from config.yaml.

    Returns:
        The loaded Settings instance.
    """
    global _settings
    _settings = Settings.load_from_yaml(Path("config.yaml"))
    return _settings
