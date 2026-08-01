"""Tests that shipped executable YAML configs load under the strict model.

Both ``config.yaml`` and ``config.example.yaml`` must parse successfully
through ``Settings.load_from_yaml`` with no unknown or legacy keys.
Documentation snippets are not executable YAML and are verified by shape
in the review process, but the shipped executable configs are tested here.
"""

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


class TestShippedConfigsLoad:
    """Shipped executable YAML configs must load under the strict Settings model."""

    def test_config_yaml_loads(self) -> None:
        path = _PROJECT_ROOT / "config.yaml"
        assert path.exists(), "config.yaml must exist"
        settings = Settings.load_from_yaml(path)
        assert settings.github.repo == "geoqiao/geoqiao.github.io"
        assert settings.site.url.scheme == "https"
        assert str(settings.site.url) == "https://geoqiao.me/"
        assert settings.security.token_env == "G_T"  # noqa: S105

    def test_config_example_yaml_loads(self) -> None:
        path = _PROJECT_ROOT / "config.example.yaml"
        assert path.exists(), "config.example.yaml must exist"
        settings = Settings.load_from_yaml(path)
        assert settings.github.repo == "username/username.github.io"
        assert settings.site.url.scheme == "https"
        assert settings.security.token_env == "G_T"  # noqa: S105
        assert settings.about.issue_number == 1

    def test_config_yaml_has_no_legacy_blog_key(self) -> None:
        """config.yaml must not contain the legacy top-level 'blog' key."""
        import yaml

        with open(_PROJECT_ROOT / "config.yaml") as f:
            data = yaml.safe_load(f)
        assert "blog" not in data, (
            "config.yaml must not contain legacy 'blog' key; use 'site' instead"
        )

    def test_config_example_yaml_has_no_legacy_blog_key(self) -> None:
        """config.example.yaml must not contain the legacy top-level 'blog' key."""
        import yaml

        with open(_PROJECT_ROOT / "config.example.yaml") as f:
            data = yaml.safe_load(f)
        assert "blog" not in data, (
            "config.example.yaml must not contain legacy 'blog' key; use 'site' instead"
        )

    def test_config_yaml_has_no_legacy_about_keys(self) -> None:
        """config.yaml 'about' must only have issue_number, not legacy keys."""
        import yaml

        with open(_PROJECT_ROOT / "config.yaml") as f:
            data = yaml.safe_load(f)
        about = data.get("about", {})
        assert set(about.keys()) == {"issue_number"}, (
            f"about must contain only issue_number, got: {set(about.keys())}"
        )

    def test_config_example_yaml_has_no_legacy_about_keys(self) -> None:
        """config.example.yaml 'about' must only have issue_number."""
        import yaml

        with open(_PROJECT_ROOT / "config.example.yaml") as f:
            data = yaml.safe_load(f)
        about = data.get("about", {})
        assert set(about.keys()) == {"issue_number"}, (
            f"about must contain only issue_number, got: {set(about.keys())}"
        )

    def test_config_yaml_has_allowed_authors(self) -> None:
        """config.yaml must have github.allowed_authors."""
        import yaml

        with open(_PROJECT_ROOT / "config.yaml") as f:
            data = yaml.safe_load(f)
        assert "allowed_authors" in data.get("github", {}), (
            "config.yaml must have github.allowed_authors"
        )

    def test_config_example_yaml_has_allowed_authors(self) -> None:
        """config.example.yaml must have github.allowed_authors."""
        import yaml

        with open(_PROJECT_ROOT / "config.example.yaml") as f:
            data = yaml.safe_load(f)
        assert "allowed_authors" in data.get("github", {}), (
            "config.example.yaml must have github.allowed_authors"
        )

    def test_config_yaml_has_no_github_username(self) -> None:
        """config.yaml must not have the legacy github.username key."""
        import yaml

        with open(_PROJECT_ROOT / "config.yaml") as f:
            data = yaml.safe_load(f)
        assert "username" not in data.get("github", {}), (
            "config.yaml must not have github.username; it is derived from repo"
        )

    def test_config_yaml_has_no_home_post_count(self) -> None:
        """config.yaml must not have home_post_count in paths."""
        import yaml

        with open(_PROJECT_ROOT / "config.yaml") as f:
            data = yaml.safe_load(f)
        paths = data.get("paths", {})
        assert "home_post_count" not in paths, (
            "config.yaml must not have paths.home_post_count; it is fixed at 5 for v1"
        )

    def test_config_yaml_has_no_paths_language(self) -> None:
        """config.yaml must not have language in paths; it is in site."""
        import yaml

        with open(_PROJECT_ROOT / "config.yaml") as f:
            data = yaml.safe_load(f)
        paths = data.get("paths", {})
        assert "language" not in paths, (
            "config.yaml must not have paths.language; use site.language"
        )

    def test_config_yaml_has_no_profile_expertise(self) -> None:
        """config.yaml profile must not have expertise (legacy key)."""
        import yaml

        with open(_PROJECT_ROOT / "config.yaml") as f:
            data = yaml.safe_load(f)
        profile = data.get("profile", {})
        assert "expertise" not in profile, (
            "config.yaml profile must not have expertise; "
            "it belongs to About Issue Content"
        )

    @pytest.mark.parametrize(
        "filename",
        [
            "README.md",
            "README_en.md",
        ],
    )
    def test_readme_config_snippet_has_no_legacy_blog_key(self, filename: str) -> None:
        """README config snippets must not reference the legacy 'blog:' section."""
        path = _PROJECT_ROOT / filename
        content = path.read_text(encoding="utf-8")
        # Look for the YAML config snippet section
        assert "blog:\n" not in content or "blog_dir" in content, (
            f"{filename} should not contain a legacy top-level 'blog:' config section"
        )


class TestNoDuplicateKeys:
    """Shipped YAML configs and documentation snippets must not have duplicate keys."""

    def test_config_example_yaml_no_duplicate_keys(self) -> None:
        """config.example.yaml must not have duplicate top-level or nested keys."""
        path = _PROJECT_ROOT / "config.example.yaml"
        content = path.read_text(encoding="utf-8")
        loader = _unique_key_loader()
        yaml.load(content, Loader=loader)  # noqa: S506 - trusted local file

    def test_config_yaml_no_duplicate_keys(self) -> None:
        """config.yaml must not have duplicate top-level or nested keys."""
        path = _PROJECT_ROOT / "config.yaml"
        content = path.read_text(encoding="utf-8")
        loader = _unique_key_loader()
        yaml.load(content, Loader=loader)  # noqa: S506 - trusted local file

    def test_migration_new_structure_yaml_no_duplicate_keys(self) -> None:
        """The migration guide 'New Structure' YAML block must have no duplicate keys."""
        path = _PROJECT_ROOT / "docs" / "migration.md"
        content = path.read_text(encoding="utf-8")
        marker = "**New Structure (required):**"
        idx = content.find(marker)
        assert idx != -1, "migration guide must contain 'New Structure' block"
        start = content.find("```yaml", idx)
        assert start != -1, "New Structure block must be a YAML code block"
        start += len("```yaml")
        end = content.find("```", start)
        assert end != -1, "New Structure YAML block must be closed"
        yaml_text = content[start:end]
        loader = _unique_key_loader()
        yaml.load(yaml_text, Loader=loader)  # noqa: S506 - trusted local file


class TestNavigationNestedUnderSite:
    """Optional navigation must be shown nested under 'site', not as a second top-level 'site'."""

    def test_config_example_navigation_nested_under_site(self) -> None:
        """config.example.yaml must show navigation nested under the existing site mapping."""
        path = _PROJECT_ROOT / "config.example.yaml"
        content = path.read_text(encoding="utf-8")
        # Count top-level 'site:' occurrences (should be exactly 1)
        top_level_site_count = sum(
            1 for line in content.splitlines() if line.rstrip() == "site:"
        )
        assert top_level_site_count == 1, (
            f"config.example.yaml should have exactly one top-level 'site:' key, "
            f"found {top_level_site_count}"
        )

    def test_migration_new_structure_navigation_nested_under_site(self) -> None:
        """The migration guide 'New Structure' YAML must have one top-level 'site:' key."""
        path = _PROJECT_ROOT / "docs" / "migration.md"
        content = path.read_text(encoding="utf-8")
        marker = "**New Structure (required):**"
        idx = content.find(marker)
        assert idx != -1
        start = content.find("```yaml", idx) + len("```yaml")
        end = content.find("```", start)
        yaml_text = content[start:end]
        top_level_site_count = sum(
            1 for line in yaml_text.splitlines() if line.rstrip() == "site:"
        )
        assert top_level_site_count == 1, (
            f"migration guide New Structure should have exactly one top-level "
            f"'site:' key, found {top_level_site_count}"
        )


class TestMigrationGuideYamlLoads:
    """The migration guide 'New Structure' YAML block must load under Settings."""

    def test_migration_new_structure_loads_under_settings(self, tmp_path: Path) -> None:
        path = _PROJECT_ROOT / "docs" / "migration.md"
        content = path.read_text(encoding="utf-8")
        marker = "**New Structure (required):**"
        idx = content.find(marker)
        assert idx != -1
        start = content.find("```yaml", idx) + len("```yaml")
        end = content.find("```", start)
        yaml_text = content[start:end]
        yaml_file = tmp_path / "migration_config.yaml"
        yaml_file.write_text(yaml_text)
        settings = Settings.load_from_yaml(yaml_file)
        assert settings.github.repo == "username/username.github.io"
        assert settings.security.token_env == "G_T"  # noqa: S105
