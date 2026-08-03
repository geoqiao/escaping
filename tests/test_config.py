from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from escaping.config import (
    BuiltinThemeConfig,
    GithubConfig,
    Link,
    LocalThemeConfig,
    PathsConfig,
    ProjectCatalogEntry,
    ProjectFallbackMetadata,
    SecurityConfig,
    Settings,
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


def test_strict_paths_have_only_output_and_page_size() -> None:
    paths = PathsConfig()
    assert paths.output == "output"
    assert paths.page_size == 10
    with pytest.raises(ValidationError):
        PathsConfig.model_validate({"unknown": "value"})


def test_theme_source_is_explicit_and_separate_from_output_paths() -> None:
    defaults = Settings.model_validate(_BASE)
    assert defaults.theme == BuiltinThemeConfig(name="geoqiao.me")

    builtin = Settings.model_validate(
        {**_BASE, "theme": {"source": "builtin", "name": "Escape1"}}
    )
    assert builtin.theme == BuiltinThemeConfig(name="Escape1")

    local = Settings.model_validate(
        {
            **_BASE,
            "theme": {
                "source": "local",
                "name": "site-theme",
                "path": "theme",
            },
        }
    )
    assert local.theme == LocalThemeConfig(name="site-theme", path=Path("theme"))

    with pytest.raises(ValidationError):
        PathsConfig.model_validate({"theme": "Escape1"})


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "//evil.example/path",
        "https://user:password@example.com/",
        "https://example.com/has space",
        "https://example.com/\nnext",
    ],
)
def test_link_rejects_unsafe_destinations(url: str) -> None:
    with pytest.raises(ValidationError):
        Link(name="unsafe", url=url)


def test_profile_and_branding_reject_unsafe_rendered_urls() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({**_BASE, "profile": {"avatar": "javascript:alert(1)"}})
    with pytest.raises(ValidationError):
        Settings.model_validate(
            {
                **_BASE,
                "branding": {"powered_by_url": "//evil.example/source"},
            }
        )
    with pytest.raises(ValidationError):
        Settings.model_validate(
            {**_BASE, "comments": {"theme": "</script><script>alert(1)"}}
        )


def test_https_origin_and_dynamic_token_name() -> None:
    assert GithubConfig(repo="o/r", allowed_authors=["A"]).username == "o"
    with pytest.raises(ValidationError):
        SecurityConfig(token_env="G-T")  # noqa: S106
    with pytest.raises(ValidationError):
        Settings.model_validate(
            {**_BASE, "site": {**_BASE["site"], "url": "http://x.test"}}
        )


@pytest.mark.parametrize(
    ("section", "value"),
    [
        ("seo", {"enable_sitemap": False}),
        ("branding", {"show_intro": True}),
        ("comments", {"provider": "utterances"}),
    ],
)
def test_removed_noop_config_fields_are_rejected(
    section: str, value: dict[str, object]
) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({**_BASE, section: value})


def test_repository_references_use_owner_repo_format() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({**_BASE, "comments": {"repo": "javascript:bad"}})
    with pytest.raises(ValidationError):
        ProjectCatalogEntry(
            slug="bad",
            title="Bad",
            repository="not-a-repository",
            summary="Bad repository reference",
        )


def test_project_fallback_contract() -> None:
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
