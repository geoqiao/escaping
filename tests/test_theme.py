from __future__ import annotations

from pathlib import Path

import pytest

from github_blog.config import ThemeLockConfig
from github_blog.theme import ThemeResolutionError, ThemeResolver


def _theme(root: Path, name: str = "locked") -> Path:
    theme = root / name
    (theme / "static" / "css").mkdir(parents=True)
    (theme / "static" / "js").mkdir()
    (theme / "static" / "images").mkdir()
    for filename in (
        "base.html",
        "home.html",
        "index.html",
        "post.html",
        "tag.html",
        "tags.html",
        "ideas.html",
        "idea.html",
        "about.html",
        "projects.html",
    ):
        (theme / filename).write_text(
            f"{filename} {{% block content %}}{{{{ value }}}}{{% endblock %}}"
        )
    (theme / "static" / "css" / "style.css").write_text("body {}")
    (theme / "theme.yaml").write_text(
        "api_version: '1'\ncapabilities: [comments]\nrequired_templates:\n"
        + "".join(
            f"  - {filename}\n"
            for filename in (
                "base.html",
                "home.html",
                "index.html",
                "post.html",
                "tag.html",
                "tags.html",
                "ideas.html",
                "idea.html",
                "about.html",
                "projects.html",
            )
        )
        + "required_assets: [static/css, static/js, static/images]\n"
    )
    return theme


def _lock() -> ThemeLockConfig:
    return ThemeLockConfig(repository="owner/theme", commit="a" * 40, api_version="1")


def test_resolver_uses_cache_and_merges_site_overrides_first(tmp_path: Path) -> None:
    locked = _theme(tmp_path / "cache" / ("a" * 40))
    override = tmp_path / "overrides"
    override.mkdir()
    (override / "base.html").write_text("override")

    source = ThemeResolver(
        tmp_path, _lock(), theme_name="locked", override_dir=override
    ).resolve()
    assert source.template_dirs[0] == override
    assert source.template_dirs[1] == locked
    assert source.read_text("base.html") == "override"
    assert source.read_text("home.html").startswith("home.html")


def test_resolver_fetches_exact_commit_only_when_cache_missing(tmp_path: Path) -> None:
    calls: list[str] = []

    def fetch(lock: ThemeLockConfig, destination: Path) -> None:
        calls.append(lock.commit)
        _theme(destination)

    source = ThemeResolver(
        tmp_path, _lock(), theme_name="locked", fetch=fetch
    ).resolve()
    assert calls == ["a" * 40]
    assert source.lock.commit == "a" * 40

    ThemeResolver(tmp_path, _lock(), theme_name="locked", fetch=fetch).resolve()
    assert calls == ["a" * 40]


def test_manifest_mismatch_and_missing_contract_fail(tmp_path: Path) -> None:
    theme = _theme(tmp_path / "cache" / ("a" * 40))
    (theme / "theme.yaml").write_text(
        "api_version: '2'\ncapabilities: []\nrequired_templates: [base.html]\nrequired_assets: []\n"
    )
    with pytest.raises(ThemeResolutionError, match="api_version"):
        ThemeResolver(tmp_path, _lock(), theme_name="locked").resolve()

    (theme / "theme.yaml").write_text(
        "api_version: '1'\ncapabilities: []\nrequired_templates: [missing.html]\nrequired_assets: []\n"
    )
    with pytest.raises(ThemeResolutionError, match=r"missing\.html"):
        ThemeResolver(tmp_path, _lock(), theme_name="locked").resolve()


@pytest.mark.parametrize("theme_name", ["Escape1", "Escape2"])
def test_shipped_locked_themes_resolve_with_manifest(theme_name: str) -> None:
    from github_blog.theme import ThemeResolver

    source = ThemeResolver(
        Path.cwd(),
        ThemeLockConfig(
            repository="owner/theme",
            commit="e30a52e89645e4e3cd0f1630653c248b9f203c7d",
            api_version="1",
        ),
        theme_name=theme_name,
    ).resolve()
    assert source.locked_dir.name == theme_name
    assert source.environment().get_template("home.html")


def test_update_is_explicit_and_strict_undefined_is_available(tmp_path: Path) -> None:
    _theme(tmp_path / "cache" / ("a" * 40))
    resolver = ThemeResolver(tmp_path, _lock(), theme_name="locked")
    assert resolver.resolve().environment().undefined.__name__ == "StrictUndefined"
    with pytest.raises(ThemeResolutionError, match="explicit"):
        resolver.update()

    new_lock = ThemeLockConfig(
        repository="owner/theme", commit="b" * 40, api_version="1"
    )
    resolver.update(new_lock, lambda lock, destination: _theme(destination))
    assert resolver.lock.commit == "b" * 40
    assert (tmp_path / "cache" / ("b" * 40)).exists()
