"""Contract tests for the Configs the project ships: the full reference and the
starter's empty Config."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from escpe.config import (
    PlatformContext,
    RepositoryIdentity,
    Settings,
    read_config_overrides,
    validate_config_overrides,
)
from escpe.services.github_service import PublicProfile
from escpe.site_compiler import prepare_theme
from escpe.site_inputs import resolve_settings

_PROJECT_ROOT = Path(__file__).parent.parent
_CONFIG_EXAMPLE = _PROJECT_ROOT / "config.example.yaml"
_STARTER_CONFIG = _PROJECT_ROOT / "starter" / "config.yaml"
_COMMENTED_KEY = re.compile(r"(\s*)# [a-z_]+:")


class _Profiles:
    def fetch_repository_identity(self, repository: str) -> RepositoryIdentity:
        owner = repository.split("/")[0]
        return RepositoryIdentity(
            repository=repository, owner_login=owner, owner_type="User"
        )

    def fetch_public_profile(self, login: str) -> PublicProfile:
        return PublicProfile(login, "Alice Example", "https://example.org/a.png", "Hi")


def _uncommented(text: str) -> str:
    """The example with every commented-out setting switched on.

    A commented setting starts with ``# key:``; the lines under it are
    commented deeper (``#   key:``) or indented further (``    # key:``).
    """
    lines: list[str] = []
    block: str | None = None
    for line in text.splitlines():
        if block is not None and (
            line.startswith(f"{block}#  ")
            or re.match(rf"{re.escape(block)}\s+# ", line)
        ):
            lines.append(line.replace("# ", "", 1))
            continue
        block = None
        if match := _COMMENTED_KEY.match(line):
            block = match.group(1)
            lines.append(line.replace("# ", "", 1))
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


def test_example_config_resolves_as_shipped() -> None:
    overrides = read_config_overrides(_CONFIG_EXAMPLE)
    settings, warnings = resolve_settings(overrides, github_service=_Profiles())

    assert not warnings
    assert settings.github.repo == "username/username.github.io"
    assert str(settings.site.url) == "https://username.github.io/"
    assert settings.theme.use == "quiet" and settings.theme.options == {}
    assert not settings.comments.enabled
    assert settings.security.token_env == "GITHUB_TOKEN"  # noqa: S105
    prepare_theme(settings, _PROJECT_ROOT)


def test_every_commented_setting_in_the_example_is_valid() -> None:
    data = yaml.safe_load(_uncommented(_CONFIG_EXAMPLE.read_text(encoding="utf-8")))

    # A full reference: every section and every Quiet option is documented.
    assert set(data) == set(Settings.model_fields)
    validate_config_overrides(data)
    settings = Settings.model_validate(data)
    theme, _ = prepare_theme(settings, _PROJECT_ROOT)
    assert set(settings.theme.options) == set(theme.options)
    assert settings.profile.bio and settings.about.issue_number == 1
    assert settings.site.navigation.items and len(settings.projects) == 2


def test_starter_config_builds_from_the_platform_context_alone() -> None:
    overrides = read_config_overrides(_STARTER_CONFIG)
    context = PlatformContext.model_validate(
        {
            "repository": "alice/alice.github.io",
            "owner_login": "alice",
            "owner_type": "User",
            "pages_base_url": "https://alice.github.io/",
        }
    )
    settings, _ = resolve_settings(
        overrides, context=context, github_service=_Profiles()
    )

    assert settings.github.repo == "alice/alice.github.io"
    assert settings.github.allowed_authors == ["alice"]
    assert settings.theme.use == "quiet"
