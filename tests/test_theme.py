from __future__ import annotations

from pathlib import Path

import pytest

from escaping.config import BuiltinThemeConfig, LocalThemeConfig
from escaping.theme import ThemeLoader, ThemeResolutionError


def _theme(root: Path, name: str = "local") -> Path:
    theme = root / name
    (theme / "static" / "css").mkdir(parents=True)
    (theme / "static" / "js").mkdir()
    (theme / "static" / "images").mkdir()
    templates = (
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
    for filename in templates:
        (theme / filename).write_text(
            f"{filename} {{% block content %}}{{{{ value }}}}{{% endblock %}}",
            encoding="utf-8",
        )
    (theme / "static" / "css" / "style.css").write_text("body {}", encoding="utf-8")
    (theme / "theme.yaml").write_text(
        "api_version: '1'\ncapabilities: [comments]\nrequired_templates:\n"
        + "".join(f"  - {filename}\n" for filename in templates)
        + "required_assets: [static/css, static/js, static/images]\n",
        encoding="utf-8",
    )
    return theme


@pytest.mark.parametrize("name", ["geoqiao.me", "Escape1", "Escape2"])
def test_builtin_theme_loads_and_copies_assets_outside_checkout(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    source = ThemeLoader(tmp_path).load(BuiltinThemeConfig(name=name))

    assert source.environment().get_template("home.html")
    assert source.environment().undefined.__name__ == "StrictUndefined"
    assert source.asset_url_path == f"/templates/{name}"
    source.copy_assets(tmp_path / "output")
    assert (
        tmp_path / "output" / "templates" / name / "static" / "css" / "style.css"
    ).is_file()


def test_local_theme_resolves_from_config_root_instead_of_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_root = tmp_path / "site"
    _theme(config_root / "themes", "custom")
    unrelated_cwd = tmp_path / "elsewhere"
    unrelated_cwd.mkdir()
    monkeypatch.chdir(unrelated_cwd)

    source = ThemeLoader(config_root).load(
        LocalThemeConfig(name="custom", path=Path("themes/custom"))
    )

    assert source.environment().get_template("home.html")
    source.copy_assets(config_root / "output")
    assert (
        config_root / "output" / "templates" / "custom" / "static" / "css" / "style.css"
    ).is_file()


def test_manifest_mismatch_missing_contract_and_unsafe_path_fail(
    tmp_path: Path,
) -> None:
    theme = _theme(tmp_path / "themes", "broken")
    declaration = LocalThemeConfig(name="broken", path=Path("themes/broken"))
    (theme / "theme.yaml").write_text(
        "api_version: '2'\ncapabilities: []\nrequired_templates: [base.html]\nrequired_assets: []\n",
        encoding="utf-8",
    )
    with pytest.raises(ThemeResolutionError, match="api_version"):
        ThemeLoader(tmp_path).load(declaration)

    (theme / "theme.yaml").write_text(
        "api_version: '1'\ncapabilities: []\nrequired_templates: [missing.html]\nrequired_assets: []\n",
        encoding="utf-8",
    )
    with pytest.raises(ThemeResolutionError, match=r"missing\.html"):
        ThemeLoader(tmp_path).load(declaration)

    (theme / "theme.yaml").write_text(
        "api_version: '1'\ncapabilities: []\nrequired_templates: []\nrequired_assets: [/tmp]\n",
        encoding="utf-8",
    )
    with pytest.raises(ThemeResolutionError, match="unsafe theme resource path"):
        ThemeLoader(tmp_path).load(declaration)
