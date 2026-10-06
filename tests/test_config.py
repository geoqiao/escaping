"""The Config: three sections are read, checked field by field; the rest is ignored."""

from __future__ import annotations

from pathlib import Path
from typing import Never

import pytest
from pydantic import ValidationError

from escaping_site.config import (
    ConfigError,
    GithubConfig,
    RepositoryIdentity,
    SecurityConfig,
    read_content_overrides,
    security_from_config,
    validate_content_overrides,
)
from escaping_site.content_inputs import resolve_content_settings

_BASE = {
    "github": {"repo": "geoqiao/site", "allowed_authors": ["geoqiao"]},
    "about": {"issue_number": 10},
    "security": {"token_env": "TOKEN"},
}


def _problems(data: object) -> list[str]:
    with pytest.raises(ConfigError) as error:
        validate_content_overrides(data)
    return error.value.problems


class _Source:
    """``bob/*`` belongs to an Organization."""

    def fetch_repository_identity(self, repository: str) -> RepositoryIdentity:
        return RepositoryIdentity(
            repository=repository,
            owner_login=repository.split("/")[0],
            owner_type="Organization" if repository.startswith("bob/") else "User",
        )


class _NoNetwork:
    def fetch_repository_identity(self, repository: str) -> Never:
        pytest.fail("an invalid Config must fail before repository access")


@pytest.mark.parametrize(
    ("data", "problem"),
    [
        (
            {"github": {"repos": "a/b"}},
            "github.repos: unknown field; did you mean repo?",
        ),
        ({"security": {"zzz": 1}}, "security.zzz: unknown field"),
        ({"about": None}, "about: is empty; remove the line or add values under it"),
        ({"about": {"issue_number": "1"}}, "about.issue_number:"),
        ({"github": {"repo": "not a repository"}}, "github.repo:"),
        ({"github": {"allowed_authors": []}}, "github.allowed_authors:"),
        ([], "Config must be a mapping"),
    ],
)
def test_config_problems_name_the_field_and_the_fix(data: object, problem: str) -> None:
    assert any(problem in line for line in _problems(data)), _problems(data)


def test_sections_of_the_site_are_neither_read_nor_checked() -> None:
    validate_content_overrides(
        {**_BASE, "site": {"titel": 1}, "pages": None, "my_frontend": ["anything"]}
    )
    settings = resolve_content_settings({**_BASE, "theme": {"use": "Quiet"}})
    assert settings.github.repo == "geoqiao/site"
    assert settings.about.issue_number == 10


@pytest.mark.parametrize(
    "data",
    [
        {"security": {"token_env": "ghp_SECRETVALUE-1"}},
        {"github": {"repo": "ghp_SECRETVALUE"}},
        {"github": {"ghp_SECRETVALUE": "ghp_SECRETVALUE"}},
        {"about": {"issue_number": "ghp_SECRETVALUE"}},
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
        ("github: {}\ngithub: {}\n", "config.yaml:2:1: the same key appears twice"),
        ("github:\n  repo: a/b\n  repo: a/c\n", "config.yaml:3:3: the same key"),
        ("github:\n  repo: [\n", "config.yaml:3:1:"),
        ("- a\n", "Config must be a mapping"),
        ("security: !!python/object:x {}\n", "config.yaml:1:11:"),
    ):
        path.write_text(text, encoding="utf-8")
        with pytest.raises(ConfigError) as error:
            read_content_overrides(path)
        assert any(expected in p for p in error.value.problems), error.value.problems
    with pytest.raises(ConfigError, match="Config file not found"):
        read_content_overrides(tmp_path / "missing.yaml")


def test_empty_config_file_is_all_defaults_and_token_env_is_a_name(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config.yaml"
    for text in ("", "null\n", "{}\n"):
        path.write_text(text, encoding="utf-8")
        assert read_content_overrides(path) == {}
    assert security_from_config({}).token_env == "GITHUB_TOKEN"  # noqa: S105
    path.write_text("security:\n  token_env: READ_TOKEN\n", encoding="utf-8")
    assert security_from_config(read_content_overrides(path)).token_env == "READ_TOKEN"  # noqa: S105
    for name in ("G-T", "TOKEN\n", "1TOKEN"):
        with pytest.raises(ValidationError):
            SecurityConfig(token_env=name)


def test_github_owner_and_allowed_authors() -> None:
    config = GithubConfig(repo="Owner/site", allowed_authors=[" Alice "])
    assert config.owner == "Owner" and config.allowed_authors == ["Alice"]
    for authors in ([], [" "], ["alice", "ALICE"]):
        with pytest.raises(ValidationError):
            GithubConfig(repo="o/r", allowed_authors=authors)


def test_the_owner_of_a_personal_repository_is_the_author_when_none_is_named() -> None:
    settings = resolve_content_settings(
        {"github": {"repo": "alice/site"}}, github_service=_Source()
    )
    assert settings.github.allowed_authors == ["alice"]

    # --repo replaces github.repo; authors that are written are kept.
    settings = resolve_content_settings(
        _BASE, repository="carol/c", github_service=_NoNetwork()
    )
    assert settings.github.repo == "carol/c"
    assert settings.github.allowed_authors == ["geoqiao"]

    with pytest.raises(ValueError, match=r"explicit for an Organization"):
        resolve_content_settings(
            {"github": {"repo": "bob/content"}}, github_service=_Source()
        )


def test_without_github_access_the_error_names_what_is_missing() -> None:
    with pytest.raises(ValueError, match=r"github\.repo"):
        resolve_content_settings({})
    with pytest.raises(ValueError, match=r"github\.allowed_authors.*needs a token"):
        resolve_content_settings({"github": {"repo": "alice/site"}})


@pytest.mark.parametrize(
    ("data", "field"),
    [
        ({"about": {"issue_number": "1"}}, "about.issue_number"),
        ({"github": {"repo": "alice/site", "authors": ["a"]}}, "github.authors"),
        ({"security": {"token_env": "a-b"}}, "security.token_env"),
    ],
)
def test_invalid_config_fails_before_any_github_access(data: dict, field: str) -> None:
    with pytest.raises(ConfigError) as error:
        resolve_content_settings(data, github_service=_NoNetwork())
    assert any(p.startswith(field) for p in error.value.problems)
