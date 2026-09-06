"""Contract tests for the generator's only shipped Config example."""

from __future__ import annotations

from pathlib import Path

from escaping.config import BuiltinThemeConfig, Settings

_PROJECT_ROOT = Path(__file__).parent.parent
_CONFIG_EXAMPLE = _PROJECT_ROOT / "config.example.yaml"


def test_example_config_strict_loads_with_default_theme() -> None:
    settings = Settings.load_from_yaml(_CONFIG_EXAMPLE)

    assert settings.site.url.scheme == "https"
    assert settings.security.token_env == "GITHUB_TOKEN"  # noqa: S105
    assert settings.about.issue_number is not None and settings.about.issue_number >= 1
    assert settings.theme == BuiltinThemeConfig(name="Quiet")
    assert not settings.comments.enabled
    assert settings.site.thesis == []
    assert settings.profile.tagline == ""
    assert settings.profile.bio == ""
