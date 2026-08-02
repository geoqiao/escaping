"""Tests that shipped executable YAML configs load under the strict model."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from yaml.resolver import BaseResolver

from github_blog.config import Settings

_PROJECT_ROOT = Path(__file__).parent.parent


def _unique_key_loader() -> type[yaml.SafeLoader]:
    """Return a SafeLoader subclass that raises on duplicate mapping keys."""

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


@pytest.mark.parametrize("filename", ["config.yaml", "config.example.yaml"])
def test_shipped_config_strict_load(filename: str) -> None:
    """Both shipped configs load under the strict Settings model."""
    path = _PROJECT_ROOT / filename
    assert path.exists(), f"{filename} must exist"
    settings = Settings.load_from_yaml(path)
    assert settings.site.url.scheme == "https"
    assert settings.security.token_env == "G_T"  # noqa: S105
    assert settings.about.issue_number >= 1
    assert settings.theme_lock is not None


@pytest.mark.parametrize("filename", ["config.yaml", "config.example.yaml"])
def test_shipped_config_has_no_duplicate_keys(filename: str) -> None:
    loader = _unique_key_loader()
    yaml_text = (_PROJECT_ROOT / filename).read_text(encoding="utf-8")
    yaml.load(yaml_text, Loader=loader)  # noqa: S506 - trusted local file
