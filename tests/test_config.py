from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from github_blog.config import (
    GithubConfig,
    PathsConfig,
    ProjectCatalogEntry,
    ProjectFallbackMetadata,
    SecurityConfig,
    Settings,
    ThemeLockConfig,
)

_BASE = {
    "github": {"repo": "geoqiao/site", "allowed_authors": ["geoqiao"]},
    "site": {"title": "Site", "author": "geoqiao", "url": "https://geoqiao.me/"},
    "about": {"issue_number": 10},
    "security": {"token_env": "TOKEN"},
}


def test_settings_reject_unknown_nested_fields() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({**_BASE, "paths": {"old_html": "x"}})
    with pytest.raises(ValidationError):
        Settings.model_validate({**_BASE, "site": {**_BASE["site"], "typo": True}})


def test_strict_paths_have_only_output_theme_and_page_size() -> None:
    paths = PathsConfig()
    assert paths.theme == "geoqiao.me"
    assert paths.page_size == 10
    with pytest.raises(ValidationError):
        PathsConfig.model_validate({"unknown": "value"})


def test_https_origin_and_dynamic_token_name() -> None:
    assert GithubConfig(repo="o/r", allowed_authors=["A"]).username == "o"
    with pytest.raises(ValidationError):
        SecurityConfig(token_env="G-T")  # noqa: S106
    with pytest.raises(ValidationError):
        Settings.model_validate(
            {**_BASE, "site": {**_BASE["site"], "url": "http://x.test"}}
        )


def test_project_and_theme_lock_contracts() -> None:
    entry = ProjectCatalogEntry(
        slug="escaping",
        title="Escaping",
        repository="geoqiao/escaping",
        summary="Compiler",
        fallback_metadata=ProjectFallbackMetadata(
            stars=1, forks=0, language="Python", topics=["tools"]
        ),
    )
    assert entry.fallback_metadata is not None
    with pytest.raises(ValidationError):
        ProjectFallbackMetadata(stars=-1)
    with pytest.raises(ValidationError):
        ThemeLockConfig(repository="o/t", commit="short", api_version="1")


def test_shipped_configs_load() -> None:
    for filename in ("config.yaml", "config.example.yaml"):
        settings = Settings.load_from_yaml(Path(filename))
        assert settings.site.url.scheme == "https"
        assert settings.about.issue_number > 0
