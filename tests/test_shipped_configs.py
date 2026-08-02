"""Tests that shipped executable YAML configs load under the strict model."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
import yaml.resolver
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


def _migration_yaml() -> str:
    """Extract the 'New Structure' YAML block from docs/migration.md."""
    content = (_PROJECT_ROOT / "docs" / "migration.md").read_text(encoding="utf-8")
    marker = "**New Structure (required):**"
    idx = content.find(marker)
    assert idx != -1, "migration guide must contain 'New Structure' block"
    start = content.find("```yaml", idx) + len("```yaml")
    end = content.find("```", start)
    assert end != -1, "New Structure YAML block must be closed"
    return content[start:end]


@pytest.mark.parametrize(
    "filename",
    ["config.yaml", "config.example.yaml"],
)
def test_shipped_config_strict_load(filename: str) -> None:
    """Both shipped configs load under the strict Settings model."""
    path = _PROJECT_ROOT / filename
    assert path.exists(), f"{filename} must exist"
    settings = Settings.load_from_yaml(path)
    assert settings.site.url.scheme == "https"
    assert settings.security.token_env == "G_T"  # noqa: S105
    assert settings.about.issue_number >= 1


@pytest.mark.parametrize(
    ("label", "yaml_text"),
    [
        ("config.yaml", (_PROJECT_ROOT / "config.yaml").read_text(encoding="utf-8")),
        (
            "config.example.yaml",
            (_PROJECT_ROOT / "config.example.yaml").read_text(encoding="utf-8"),
        ),
        ("migration New Structure", _migration_yaml()),
    ],
)
def test_no_duplicate_keys(label: str, yaml_text: str) -> None:
    """Shipped configs and migration New Structure YAML have no duplicate keys."""
    loader = _unique_key_loader()
    yaml.load(yaml_text, Loader=loader)  # noqa: S506 - trusted local file


def test_migration_yaml_instantiates_settings(tmp_path: Path) -> None:
    """The migration 'New Structure' YAML instantiates Settings."""
    yaml_file = tmp_path / "migration_config.yaml"
    yaml_file.write_text(_migration_yaml())
    settings = Settings.load_from_yaml(yaml_file)
    assert settings.github.repo == "username/username.github.io"
    assert settings.security.token_env == "G_T"  # noqa: S105
