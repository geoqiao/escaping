from __future__ import annotations

import re
from pathlib import Path
from typing import Never

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


def test_project_catalog_visual_fields_use_safe_urls_and_defaults() -> None:
    entry = ProjectCatalogEntry.model_validate(
        {
            "repository": "owner/project",
            "image": "/templates/my-theme/static/images/project.webp",
            "links": [{"name": "Demo", "url": "https://example.org/"}],
        }
    )
    assert entry.image == "/templates/my-theme/static/images/project.webp"
    assert [(link.name, link.url) for link in entry.links] == [
        ("Demo", "https://example.org/")
    ]
    defaults = ProjectCatalogEntry(repository="owner/other")
    assert defaults.image == "" and defaults.links == []
    with pytest.raises(ValidationError):
        ProjectCatalogEntry(repository="owner/project", image="javascript:bad")


def test_theme_source_is_explicit_and_separate_from_output_paths() -> None:
    defaults = Settings.model_validate(_BASE)
    assert defaults.theme == BuiltinThemeConfig(name="Quiet")

    builtin = Settings.model_validate(
        {**_BASE, "theme": {"source": "builtin", "name": "Quiet"}}
    )
    assert builtin.theme == BuiltinThemeConfig(name="Quiet")

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
        PathsConfig.model_validate({"theme": "Quiet"})


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


def test_social_image_defaults_and_accepts_safe_resource_urls() -> None:
    defaults = Settings.model_validate(_BASE)
    assert defaults.seo.social_image == ""
    assert defaults.seo.social_image_alt == ""

    for image in (
        "https://raw.githubusercontent.com/owner/site/abc/assets/social/og.png",
        "/templates/Quiet/static/images/og.png",
    ):
        settings = Settings.model_validate(
            {
                **_BASE,
                "seo": {"social_image": image, "social_image_alt": "Preview"},
            }
        )
        assert settings.seo.social_image == image
        assert settings.seo.social_image_alt == "Preview"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org/og.png",
        "mailto:image@example.org",
        "#og-image",
        "//evil.example/og.png",
        "https://user:password@example.org/og.png",
        "https://example.org/og\n.png",
    ],
)
def test_social_image_reuses_safe_resource_url_boundary(url: str) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({**_BASE, "seo": {"social_image": url}})


@pytest.mark.parametrize(
    "thesis",
    [
        ["A deliberate line.", "   "],
        ["A deliberate line.", 42],
    ],
)
def test_site_thesis_rejects_blank_or_non_string_lines(thesis: object) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({**_BASE, "site": {**_BASE["site"], "thesis": thesis}})


def test_https_origin_and_dynamic_token_name() -> None:
    assert GithubConfig(repo="o/r", allowed_authors=["A"]).username == "o"
    for token_env in ("G-T", "TOKEN\n"):
        with pytest.raises(ValidationError):
            SecurityConfig(token_env=token_env)
    with pytest.raises(ValidationError):
        Settings.model_validate(
            {**_BASE, "site": {**_BASE["site"], "url": "http://x.test"}}
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://example.org\\nested",
        "https://exa\nmple.org/",
        123,
        "https://example.org/nested/",
    ],
)
def test_canonical_origin_rejects_unsafe_or_non_root_input(url: object) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({**_BASE, "site": {**_BASE["site"], "url": url}})


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


def test_comments_require_an_explicit_boolean_opt_in() -> None:
    assert not Settings.model_validate(_BASE).comments.enabled
    for enabled in (True, False):
        settings = Settings.model_validate(
            {**_BASE, "comments": {"enabled": enabled, "repo": ""}}
        )
        assert settings.comments.enabled is enabled
    for invalid in (None, "true", "false", 1, 0, [], {}):
        with pytest.raises(ValidationError):
            Settings.model_validate({**_BASE, "comments": {"enabled": invalid}})


def test_repository_references_use_owner_repo_format() -> None:
    with pytest.raises(ValidationError) as missing:
        ProjectCatalogEntry.model_validate({})
    assert any(
        error["type"] == "missing" and error["loc"] == ("repository",)
        for error in missing.value.errors()
    )
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


def test_resolver_sources_preserve_overrides_and_require_trusted_authors() -> None:
    from escaping.config import PlatformContext, RepositoryIdentity
    from escaping.services.github_service import PublicProfile
    from escaping.site_inputs import resolve_settings

    context = PlatformContext.model_validate(
        {
            "repository": "alice/site",
            "owner_login": "alice",
            "owner_type": "User",
            "pages_base_url": "https://notes.example/",
            "pages_base_path": "/",
        }
    )

    class Source:
        def fetch_repository_identity(self, repository: str) -> RepositoryIdentity:
            return RepositoryIdentity(
                repository=repository,
                owner_login=repository.split("/")[0],
                owner_type="Organization" if repository.startswith("bob/") else "User",
            )

        def fetch_public_profile(self, login: str) -> PublicProfile:
            return PublicProfile(
                login, f"{login.title()} Example", "https://example.org/a.png", "Hello"
            )

    source = Source()
    settings, warnings = resolve_settings({}, context=context, github_service=source)
    assert not warnings
    assert settings.github.allowed_authors == ["alice"]
    assert settings.site.title == settings.site.author == "Alice Example"
    assert str(settings.site.url) == "https://notes.example/"
    assert settings.profile.bio == settings.site.description == "Hello"
    partial, _ = resolve_settings(
        {"github": {}, "site": {}, "projects": [{"repository": "Alice/Tool"}]},
        context=context,
        github_service=source,
    )
    assert partial.github == settings.github and partial.site == settings.site
    assert partial.projects[0].slug == "alice/tool"
    overrides = {
        "site": {"description": "", "navigation": {"items": []}},
        "profile": {"avatar": "", "bio": ""},
        "projects": [],
        "branding": {"show_powered_by": False},
        "theme": {"name": "Quiet"},
    }
    settings, _ = resolve_settings(overrides, context=context, github_service=source)
    assert (
        settings.site.description
        == settings.profile.avatar
        == settings.profile.bio
        == ""
    )
    assert not settings.site.navigation.items and not settings.projects
    assert not settings.branding.show_powered_by and settings.theme.name == "Quiet"
    assert overrides["site"] == {"description": "", "navigation": {"items": []}}
    with pytest.raises(ValueError, match=r"github\.allowed_authors"):
        resolve_settings(
            {"github": {"repo": "bob/content"}}, context=context, github_service=source
        )
    settings, _ = resolve_settings(
        {"github": {"repo": "bob/content", "allowed_authors": [" Carol "]}},
        context=context,
        github_service=source,
    )
    assert settings.github.allowed_authors == ["Carol"]
    assert (
        settings.github.repo == "bob/content" and settings.site.author == "Bob Example"
    )
    assert str(settings.site.url) == "https://notes.example/"
    settings, _ = resolve_settings(
        {},
        context=context,
        github_service=source,
        repository_override="carol/content",
    )
    assert settings.github.allowed_authors == ["carol"]
    assert settings.site.author == "Carol Example"
    # No context is needed when the actual URL and repository are explicit.
    settings, _ = resolve_settings(
        {
            "github": {"repo": "carol/content"},
            "site": {"url": "https://notes.example/"},
        },
        github_service=source,
    )
    assert settings.github.allowed_authors == ["carol"]


@pytest.mark.parametrize(
    "data",
    [
        {"site": None},
        {"site": {"url": 123}},
        {"profile": {"avatar": None}},
        {"paths": {"typo": True}},
        {"security": {"token_env": "TOKEN\n"}},
        {"about": {"issue_number": None}},
        {"projects": [{"repository": "alice/tool", "title": None}]},
        {"site": {"url": "https://example.org\\nested"}},
        {"site": {"url": "https://exa\nmple.org/"}},
    ],
)
def test_resolver_rejects_invalid_explicit_values_before_enrichment(data: dict) -> None:
    from escaping.site_inputs import resolve_settings

    with pytest.raises(ValueError, match=r"Invalid Config fields|explicit null"):
        resolve_settings(data)


@pytest.mark.parametrize(
    ("data", "field"),
    [
        ({"projects": [{}]}, "projects.0.repository"),
        ({"site": {"navigation": {"items": [{}]}}}, "site.navigation.items.0.name"),
        (
            {"site": {"navigation": {"items": [{"name": "Blog"}]}}},
            "site.navigation.items.0.url",
        ),
        (
            {"profile": {"links": [{"url": "https://example.org/"}]}},
            "profile.links.0.name",
        ),
        ({"profile": {"links": [{"name": "Profile"}]}}, "profile.links.0.url"),
        ({"theme": {"source": "local", "path": "theme"}}, "theme.local.name"),
        ({"theme": {"source": "local", "name": "custom"}}, "theme.local.path"),
    ],
)
def test_non_defaultable_missing_fields_fail_before_profile_source(
    data: dict, field: str
) -> None:
    from escaping.config import PlatformContext, validate_config_overrides
    from escaping.site_inputs import resolve_settings

    class NoNetwork:
        def fetch_repository_identity(self, repository: str) -> Never:
            pytest.fail("Invalid Config must fail before repository access")

        def fetch_public_profile(self, login: str) -> Never:
            pytest.fail("Invalid Config must fail before Profile access")

    context = PlatformContext.model_validate(
        {
            "repository": "alice/site",
            "owner_login": "alice",
            "owner_type": "User",
            "pages_base_url": "https://notes.example/",
            "pages_base_path": "/",
        }
    )
    with pytest.raises(ValueError, match=re.escape(field)):
        validate_config_overrides(data)
    with pytest.raises(ValueError, match=re.escape(field)):
        resolve_settings(data, context=context, github_service=NoNetwork())


def test_context_and_missing_information_are_not_guessed(tmp_path: Path) -> None:
    from escaping.config import PlatformContext, read_platform_context
    from escaping.site_inputs import resolve_settings

    valid = {
        "repository": "alice/site",
        "owner_login": "alice",
        "owner_type": "User",
        "pages_base_url": "https://example.org/",
        "pages_base_path": "",
    }
    for patch in (
        {"owner_login": "mallory"},
        {"owner_type": "Bot"},
        {"actor": "alice"},
        {"pages_base_path": "/blog/"},
        {"pages_base_url": "https://example.org/blog/"},
        {"pages_base_url": "https://exa\nmple.org/"},
        {"pages_base_url": 123},
    ):
        with pytest.raises(ValidationError):
            PlatformContext.model_validate({**valid, **patch})
    with pytest.raises(ValueError, match=r"github\.repo.*site\.url"):
        resolve_settings({})
    # Fully explicit config needs neither context nor any network collaborator.
    complete = {
        **_BASE,
        "site": {**_BASE["site"], "description": ""},
        "profile": {"avatar": "", "bio": ""},
    }
    settings, warnings = resolve_settings(complete)
    assert settings.github.repo == "geoqiao/site" and not warnings
    context_path = tmp_path / "context.json"
    context_path.write_text(
        '{"repository": "alice/site", "repository": "bob/site"}', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="unique fields"):
        read_platform_context(context_path)


def test_safe_config_reader_is_shared_with_pre_settings_security(
    tmp_path: Path,
) -> None:
    from escaping.config import read_config_overrides, security_from_config

    path = tmp_path / "config.yaml"
    path.write_text("{}", encoding="utf-8")
    assert security_from_config(read_config_overrides(path)).token_env == "GITHUB_TOKEN"  # noqa: S105
    path.write_text("security:\n  token_env: READ_TOKEN\n", encoding="utf-8")
    assert security_from_config(read_config_overrides(path)).token_env == "READ_TOKEN"  # noqa: S105
    for invalid in (
        "null",
        "[]",
        "site: {}\nsite: {}",
        "security: !!python/object:bad {}",
        "security: null",
    ):
        path.write_text(invalid, encoding="utf-8")
        with pytest.raises(ValueError):
            security_from_config(read_config_overrides(path))
