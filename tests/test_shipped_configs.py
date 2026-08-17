"""Contract tests for the generator's only shipped Config example."""

from __future__ import annotations

from pathlib import Path

import yaml
from yaml.resolver import BaseResolver

from escaping.config import BuiltinThemeConfig, Settings

_PROJECT_ROOT = Path(__file__).parent.parent
_CONFIG_EXAMPLE = _PROJECT_ROOT / "config.example.yaml"


def _unique_key_loader() -> type[yaml.SafeLoader]:
    class UniqueKeyLoader(yaml.SafeLoader):
        pass

    def construct_mapping(
        loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
    ) -> dict:
        mapping: dict = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in mapping:
                raise ValueError(f"Duplicate key: {key!r}")
            mapping[key] = loader.construct_object(value_node, deep=True)
        return mapping

    UniqueKeyLoader.add_constructor(BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
    return UniqueKeyLoader


def test_example_config_strict_loads_with_default_theme() -> None:
    settings = Settings.load_from_yaml(_CONFIG_EXAMPLE)

    assert settings.site.url.scheme == "https"
    assert settings.security.token_env == "GITHUB_TOKEN"  # noqa: S105
    assert settings.about.issue_number >= 1
    assert settings.theme == BuiltinThemeConfig(name="geoqiao.me")
    assert settings.site.thesis == []
    assert settings.profile.tagline == ""
    assert settings.profile.bio == ""


def test_example_config_has_no_duplicate_keys() -> None:
    yaml.load(
        _CONFIG_EXAMPLE.read_text(encoding="utf-8"),
        Loader=_unique_key_loader(),  # noqa: S506 - trusted local file
    )
