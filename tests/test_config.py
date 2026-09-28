from __future__ import annotations

import json
from pathlib import Path
from typing import Never

import pytest
from pydantic import ValidationError

from escaping.config import (
    ConfigError,
    GithubConfig,
    Link,
    PlatformContext,
    ProjectCatalogEntry,
    ProjectFallbackMetadata,
    RepositoryIdentity,
    SecurityConfig,
    Settings,
    read_config_overrides,
    read_platform_context,
    security_from_config,
    validate_config_overrides,
)
from escaping.routes import Sections
from escaping.services.github_service import PublicProfile
from escaping.site_inputs import resolve_settings

_BASE = {
    "github": {"repo": "geoqiao/site", "allowed_authors": ["geoqiao"]},
    "site": {"title": "Site", "author": "geoqiao", "url": "https://geoqiao.me/"},
    "about": {"issue_number": 10},
    "security": {"token_env": "TOKEN"},
}
_CONTEXT = {
    "repository": "alice/site",
    "owner_login": "alice",
    "owner_type": "User",
    "pages_base_url": "https://notes.example/",
}


def _problems(data: object) -> list[str]:
    with pytest.raises(ConfigError) as error:
        validate_config_overrides(data)
    return error.value.problems


class _Source:
    """Repository/profile source; ``bob/*`` belongs to an Organization."""

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


class _NoNetwork:
    def fetch_repository_identity(self, repository: str) -> Never:
        pytest.fail("an invalid Config must fail before repository access")

    def fetch_public_profile(self, login: str) -> Never:
        pytest.fail("an invalid Config must fail before Profile access")


@pytest.mark.parametrize(
    ("data", "problem"),
    [
        ({"sitee": {}}, "sitee: unknown field; did you mean site?"),
        ({"site": {"titel": "x"}}, "site.titel: unknown field; did you mean title?"),
        ({"paths": {"zzz": 1}}, "paths.zzz: unknown field"),
        ({"about": None}, "about: is empty; remove the line or add values under it"),
        (
            {"site": {"navigation": {"items": [{"name": "Blog"}]}}},
            "items.0.url: required",
        ),
        ({"pages": {"blog": False}}, "pages.blog: the Blog cannot be turned off"),
        (
            {"pages": {"tags": "tags"}},
            "pages.tags: use a path of lowercase segments ending with /, like "
            "/tags/, or false to turn the page off",
        ),
        ({"pages": {"ideas": "/assets/x/"}}, "pages.ideas: /assets/ is reserved"),
        (
            {"pages": {"blog": "/notes/", "ideas": "/notes/"}},
            "pages: blog and ideas use the same path /notes/",
        ),
        (
            {"pages": {"tags": "/blog/tags/"}},
            "pages: blog (/blog/) and tags (/blog/tags/) must not be inside each other",
        ),
        (
            {"pages": {"extra": [{"path": "/blog/x/", "template": "x.html"}]}},
            "extra.0.path /blog/x/ is inside blog (/blog/), which owns every address",
        ),
        (
            {"pages": {"extra": [{"path": "/about/", "template": "x.html"}]}},
            "extra.0.path /about/ is already the about page",
        ),
        (
            {"pages": {"extra": [{"path": "/Now/", "template": "now.html"}]}},
            "pages.extra.0.path: use lowercase segments ending with /",
        ),
        (
            {"pages": {"extra": [{"path": "/now/", "template": "../now.html"}]}},
            "pages.extra.0.template: use a template file name in the Theme",
        ),
        (
            {"pages": {"extra": [{"path": "/w/{slug}/", "template": "w.html"}]}},
            "pages.extra.0: use {slug} in path exactly once with for_each: projects",
        ),
        (
            {**_BASE, "pages": {"about": False}},
            "about.issue_number is set but pages.about is false",
        ),
        (
            {"redirects": {"/blog/old": "/blog/new/"}},
            "redirects: end the old address with / (it then covers /old and /old/)",
        ),
        ({"redirects": {"/assets/a/": "/"}}, "redirects: /assets/ is reserved"),
        ({"redirects": {"/404.html": "/"}}, "redirects: /404.html cannot redirect"),
        ({"redirects": {"/a b/": "/"}}, "redirects: use a path of this site"),
        ({"redirects": {"/a/?x=1": "/"}}, "redirects: use a path of this site"),
        ({"redirects": {"/a/": "https://x.example/"}}, "use a path of this site"),
        ({"redirects": {"/a/../b/": "/"}}, "redirects: use a path of this site"),
        ({"redirects": {"/%ff/": "/"}}, "redirects: a redirect address has an invalid"),
        (
            {"redirects": {"/Old/": "/", "/old/": "/"}},
            "redirects: /old/ is listed twice (addresses ignore case here)",
        ),
        (
            {"redirects": {"/a/": "/b/", "/b/": "/a/"}},
            "redirects: /a/ redirects in a circle",
        ),
    ],
)
def test_config_problems_name_the_field_and_the_fix(data: dict, problem: str) -> None:
    assert any(problem in line for line in _problems(data)), _problems(data)


@pytest.mark.parametrize(
    "data",
    [
        {"security": {"token_env": "ghp_SECRETVALUE-1"}},
        {"site": {"url": "https://user:ghp_SECRETVALUE@example.com/"}},
        {"paths": {"page_size": "ghp_SECRETVALUE"}},
        {"site": {"ghp_SECRETVALUE": "ghp_SECRETVALUE"}},
        {"comments": {"repo": "ghp_SECRETVALUE"}},
    ],
)
def test_config_problems_never_echo_supplied_values(data: dict) -> None:
    problems = _problems(data)
    assert problems
    # The unknown key itself is named; its value never is.
    assert not any("ghp_SECRETVALUE" in p.split(":", 1)[1] for p in problems)


def test_config_file_errors_point_at_the_line(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    for text, expected in (
        ("site: {}\nsite: {}\n", "config.yaml:2:1: the same key appears twice"),
        ("site:\n  title: a\n  title: b\n", "config.yaml:3:3: the same key appears"),
        ("site:\n  title: [\n", "config.yaml:3:1:"),
        ("- a\n", "Config must be a mapping"),
        ("security: !!python/object:x {}\n", "config.yaml:1:11:"),
    ):
        path.write_text(text, encoding="utf-8")
        with pytest.raises(ConfigError) as error:
            read_config_overrides(path)
        assert any(expected in p for p in error.value.problems), error.value.problems
    with pytest.raises(ConfigError, match="Config file not found"):
        read_config_overrides(tmp_path / "missing.yaml")


def test_empty_config_file_is_all_defaults_and_token_env_is_a_name(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config.yaml"
    for text in ("", "null\n", "{}\n"):
        path.write_text(text, encoding="utf-8")
        assert read_config_overrides(path) == {}
    assert security_from_config({}).token_env == "GITHUB_TOKEN"  # noqa: S105
    path.write_text("security:\n  token_env: READ_TOKEN\n", encoding="utf-8")
    assert security_from_config(read_config_overrides(path)).token_env == "READ_TOKEN"  # noqa: S105
    for name in ("G-T", "TOKEN\n", "1TOKEN"):
        with pytest.raises(ValidationError):
            SecurityConfig(token_env=name)


@pytest.mark.parametrize(
    ("use", "problem"),
    [
        ("Quiet", "use a built-in Theme name such as quiet, a directory path"),
        ("my theme", "use a built-in Theme name"),
        ("../theme", "must stay inside the site repository"),
        ("/srv/theme", "must stay inside the site repository"),
        ("themes\\x/y", "must stay inside the site repository"),
        ("github.com/alice/themes/paper", "add the version to use after @"),
        ("github.com/alice@v1", "write github.com/OWNER/REPOSITORY/FOLDER@VERSION"),
        ("github.com/alice/themes/../x@v1", "cannot be . or contain .."),
        ("github.com/alice/themes@v1..2", "cannot be . or contain .."),
        ("github.com/alice/themes/paper@", "write github.com/OWNER/REPOSITORY"),
    ],
)
def test_theme_use_is_a_builtin_name_a_directory_or_a_github_address(
    use: str, problem: str
) -> None:
    assert any(problem in p for p in _problems({"theme": {"use": use}}))


@pytest.mark.parametrize(
    "use",
    [
        "github.com/alice/themes@v1.0.0",
        "github.com/alice/themes/paper@v1.0.0",
        "github.com/a-b/my.themes/set/paper@0123456789abcdef0123456789abcdef01234567",
    ],
)
def test_a_github_theme_address_is_accepted(use: str) -> None:
    assert Settings.model_validate({**_BASE, "theme": {"use": use}}).theme.use == use


def test_theme_defaults_to_quiet_and_keeps_options_for_the_theme() -> None:
    default = Settings.model_validate(_BASE).theme
    assert (default.use, default.options) == ("quiet", {})
    local = Settings.model_validate(
        {**_BASE, "theme": {"use": "./site-theme", "options": {"anything": [1]}}}
    ).theme
    # Options are checked against the Theme's theme.yaml later, not here.
    assert local.options == {"anything": [1]}


def test_projects_accept_a_repository_a_website_or_both() -> None:
    repository_only = ProjectCatalogEntry(repository="geoqiao/Some.Tool_v2")
    assert repository_only.slug == "some-tool-v2"
    assert repository_only.title == "Some.Tool_v2"
    website_only = ProjectCatalogEntry(
        website="https://example.com/", slug="site", title="Site"
    )
    assert website_only.repository == ""
    entry = ProjectCatalogEntry.model_validate(
        {
            "repository": "owner/project",
            "image": "/assets/images/project.webp",
            "links": [{"name": "Demo", "url": "https://example.org/"}],
            "fallback_metadata": {"stars": 1, "language": "Python"},
        }
    )
    assert entry.image == "/assets/images/project.webp"
    assert [(link.name, link.url) for link in entry.links] == [
        ("Demo", "https://example.org/")
    ]
    with pytest.raises(ValidationError):
        ProjectFallbackMetadata(stars=-1)


@pytest.mark.parametrize(
    ("projects", "problem"),
    [
        ([{}], "projects.0: a project needs a repository, a website, or both"),
        (
            [{"website": "https://example.com/"}],
            "projects.0: a project without a repository needs a slug",
        ),
        (
            [{"website": "http://example.com/", "slug": "x", "title": "X"}],
            "projects.0.website:",
        ),
        (
            [{"repository": "a/tool"}, {"repository": "b/Tool"}],
            "projects share the slug tool; set a distinct slug for each",
        ),
        ([{"repository": "not-a-repository"}], "use the owner/repo format"),
        ([{"repository": "a/b", "slug": "Bad Slug"}], "slug must use lowercase"),
        ([{"repository": "a/b", "image": "javascript:x"}], "projects.0.image:"),
        ([{"repository": "a/b", "featured": "yes"}], "projects.0.featured:"),
    ],
)
def test_project_problems(projects: list[dict], problem: str) -> None:
    problems = _problems({"projects": projects})
    assert any(problem in p for p in problems), problems


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


@pytest.mark.parametrize(
    ("image", "valid"),
    [
        ("https://raw.githubusercontent.com/o/s/abc/og.png", True),
        ("/assets/images/og.png", True),
        ("http://example.org/og.png", False),
        ("mailto:image@example.org", False),
        ("#og-image", False),
        ("//evil.example/og.png", False),
        ("https://example.org/og\n.png", False),
    ],
)
def test_resource_urls_are_https_or_root_relative(image: str, valid: bool) -> None:
    for data in ({"seo": {"social_image": image}}, {"profile": {"avatar": image}}):
        if valid:
            Settings.model_validate({**_BASE, **data})
        else:
            with pytest.raises(ValidationError):
                Settings.model_validate({**_BASE, **data})


@pytest.mark.parametrize(
    "url",
    [
        "http://x.test/",
        "https://example.org\\nested",
        "https://exa\nmple.org/",
        123,
        "https://example.org/a b/",
        "https://example.org/../x/",
        "https://example.org/notes/?x=1",
    ],
)
def test_site_url_must_be_an_https_url(url: object) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({**_BASE, "site": {**_BASE["site"], "url": url}})


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://example.org", "https://example.org/"),
        ("https://example.org/notes", "https://example.org/notes/"),
        ("https://alice.github.io/My.Site_2/", "https://alice.github.io/My.Site_2/"),
    ],
)
def test_site_url_may_have_a_path_and_always_ends_with_a_slash(
    url: str, expected: str
) -> None:
    settings = Settings.model_validate({**_BASE, "site": {**_BASE["site"], "url": url}})
    assert str(settings.site.url) == expected


def test_comments_require_an_explicit_boolean_opt_in() -> None:
    assert not Settings.model_validate(_BASE).comments.enabled
    assert Settings.model_validate(
        {**_BASE, "comments": {"enabled": True}}
    ).comments.enabled
    for invalid in ("true", 1, [], {}):
        with pytest.raises(ValidationError):
            Settings.model_validate({**_BASE, "comments": {"enabled": invalid}})


def test_github_owner_and_allowed_authors() -> None:
    config = GithubConfig(repo="Owner/site", allowed_authors=[" Alice "])
    assert config.owner == "Owner" and config.allowed_authors == ["Alice"]
    for authors in ([], [" "], ["alice", "ALICE"]):
        with pytest.raises(ValidationError):
            GithubConfig(repo="o/r", allowed_authors=authors)


def test_resolver_fills_only_missing_fields_from_trusted_sources() -> None:
    context = PlatformContext.model_validate(_CONTEXT)
    settings, warnings = resolve_settings({}, context=context, github_service=_Source())
    assert not warnings
    assert settings.github.allowed_authors == ["alice"]
    assert settings.site.title == settings.site.author == "Alice Example"
    assert str(settings.site.url) == "https://notes.example/"
    assert settings.profile.bio == settings.site.description == "Hello"

    overrides = {
        "site": {"description": "", "navigation": {"items": []}},
        "profile": {"avatar": "", "bio": ""},
        "theme": {"options": {"tagline": "kept"}},
    }
    settings, _ = resolve_settings(overrides, context=context, github_service=_Source())
    assert settings.site.description == settings.profile.bio == ""
    assert not settings.site.navigation.items
    assert settings.theme.options == {"tagline": "kept"}
    assert overrides["site"] == {"description": "", "navigation": {"items": []}}

    # Another owner's content repository: its owner, not the Pages owner.
    settings, _ = resolve_settings(
        {}, context=context, github_service=_Source(), repository_override="carol/c"
    )
    assert settings.github.allowed_authors == ["carol"]
    assert settings.site.author == "Carol Example"
    with pytest.raises(ValueError, match=r"github\.allowed_authors"):
        resolve_settings(
            {"github": {"repo": "bob/content"}},
            context=context,
            github_service=_Source(),
        )


def test_resolver_without_github_access_names_what_it_would_read() -> None:
    with pytest.raises(ValueError, match=r"github\.repo.*site\.url"):
        resolve_settings({})
    explicit = {
        **_BASE,
        "site": {**_BASE["site"], "description": ""},
        "profile": {"avatar": ""},
    }
    with pytest.raises(ValueError, match=r"reading profile\.bio from GitHub needs"):
        resolve_settings(explicit)
    explicit["profile"] = {"avatar": "", "bio": ""}
    settings, warnings = resolve_settings(explicit)
    assert settings.github.repo == "geoqiao/site" and not warnings


@pytest.mark.parametrize(
    ("data", "field"),
    [
        ({"site": {"url": 123}}, "site.url"),
        ({"profile": {"avatar": None}}, "profile.avatar"),
        ({"about": {"issue_number": "1"}}, "about.issue_number"),
        ({"projects": [{}]}, "projects.0"),
        ({"profile": {"links": [{"name": "Profile"}]}}, "profile.links.0.url"),
        ({"theme": {"use": "Quiet"}}, "theme.use"),
    ],
)
def test_invalid_config_fails_before_any_github_access(data: dict, field: str) -> None:
    context = PlatformContext.model_validate(_CONTEXT)
    with pytest.raises(ConfigError) as error:
        resolve_settings(data, context=context, github_service=_NoNetwork())
    assert any(p.startswith(field) for p in error.value.problems)


def test_platform_context_is_validated_without_echoing_values(tmp_path: Path) -> None:
    path = tmp_path / "context.json"
    for patch, problem in (
        ({"pages_base_url": "https://secret-host.example/a b/"}, "pages_base_url:"),
        ({"owner_login": "secret-login"}, "must identify the same owner"),
        ({"owner_type": "Bot"}, "owner_type:"),
        ({"actor": "secret-actor"}, "actor: unknown field"),
    ):
        path.write_text(json.dumps({**_CONTEXT, **patch}), encoding="utf-8")
        with pytest.raises(ConfigError) as error:
            read_platform_context(path)
        text = "\n".join(error.value.problems)
        assert problem in text and "secret" not in text
    path.write_text('{"repository": "a/b", "repository": "c/d"}', encoding="utf-8")
    with pytest.raises(ConfigError, match="unique fields"):
        read_platform_context(path)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError, match=r"context\.json:"):
        read_platform_context(path)


def test_pages_default_to_every_section_and_accept_true_false_or_a_path() -> None:
    default = Settings.model_validate(_BASE).pages
    assert default.sections() == Sections()
    assert default.extra == []

    data = {
        **_BASE,
        "about": {},
        "pages": {
            "blog": "/posts/",
            "ideas": True,
            "tags": False,
            "about": False,
            "extra": [
                {"path": "/tags/", "template": "topics.html"},
                {
                    "path": "/projects/{slug}/",
                    "template": "projects/{slug}.html",
                    "for_each": "projects",
                },
            ],
        },
    }
    settings = Settings.model_validate(data)
    assert settings.pages.sections() == Sections(
        blog="/posts/", ideas="/ideas/", tags=None, about=None
    )
    # An address a section no longer uses is free for another page.
    assert settings.pages.extra[0].path == "/tags/"
    assert settings.pages.extra[1].template_for("tool") == "projects/tool.html"
    assert [link.url for link in settings.navigation] == [
        "/",
        "/posts/",
        "/projects/",
        "/atom.xml",
    ]
