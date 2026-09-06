from __future__ import annotations

from pathlib import Path

import pytest

from escaping.config import BuiltinThemeConfig, LocalThemeConfig
from escaping.theme import ThemeLoader, ThemeResolutionError

_MERMAID_VENDOR = "static/vendor/mermaid-11.16.1"


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
        "api_version: '2'\ncapabilities: [comments]\nrequired_templates:\n"
        + "".join(f"  - {filename}\n" for filename in templates)
        + "required_assets: [static/css, static/js, static/images]\n",
        encoding="utf-8",
    )
    return theme


def test_builtin_theme_loads_and_copies_assets_outside_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    name = "Quiet"
    monkeypatch.chdir(tmp_path)

    source = ThemeLoader(tmp_path).load(BuiltinThemeConfig(name=name))

    assert source.manifest.api_version == "2"
    assert source.environment().get_template("home.html")
    assert source.environment().undefined.__name__ == "StrictUndefined"
    assert not source.resource_root.joinpath("static/js/mermaid.js").is_file()
    assert not source.resource_root.joinpath(_MERMAID_VENDOR).is_dir()
    source.copy_assets(tmp_path / "output")
    static = tmp_path / "output" / "templates" / name / "static"
    assert (static / "css" / "style.css").is_file()
    assert (static / "js" / "comments.js").is_file()
    assert (static / "js" / "mermaid.js").is_file()
    assert (static / "vendor/mermaid-11.16.1/mermaid.min.js").is_file()
    assert (static / "vendor/mermaid-11.16.1/LICENSE").is_file()
    assert (static / "vendor/mermaid-11.16.1/README.md").is_file()


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


def test_old_api_and_undefined_context_fail_without_replacing_output(
    tmp_path: Path,
) -> None:
    from escaping.config import Settings
    from escaping.models.issue_snapshot import IssueSnapshot
    from escaping.site_compiler import SiteCompiler

    class Source:
        def get_repo(self, name: str) -> object:
            return object()

        def fetch_issue_snapshots(self, repo: object) -> list[IssueSnapshot]:
            return []

    theme = _theme(tmp_path, "theme")
    manifest = theme / "theme.yaml"
    current = manifest.read_text()
    settings = Settings.model_validate(
        {
            "github": {"repo": "owner/site", "allowed_authors": ["owner"]},
            "site": {"title": "Site", "author": "Owner", "url": "https://example.org/"},
            "theme": {"source": "local", "name": "custom", "path": "theme"},
        }
    )
    output = tmp_path / "output"
    output.mkdir()
    sentinel = output / "index.html"
    sentinel.write_text("Old output remains readable.")
    compiler = SiteCompiler(
        "unused",
        settings.github.repo,
        settings,
        config_root=tmp_path,
        github_service=Source(),
    )
    manifest.write_text(current.replace("api_version: '2'", "api_version: '1'"))
    result = compiler.generate()
    assert not result.success
    assert any(
        d.code == "BUILD_FAILED"
        and "api_version '1'" in d.message
        and "expected '2'" in d.message
        for d in result.diagnostics
    )
    manifest.write_text(current)
    result = compiler.generate()
    assert not result.success
    assert any(
        d.code == "TEMPLATE_RENDER_FAILED" and "value" in d.message
        for d in result.diagnostics
    )
    assert list(output.iterdir()) == [sentinel]
    assert sentinel.read_text() == "Old output remains readable."


@pytest.mark.parametrize("name", ["geoqiao.me", "Escape1", "Escape2"])
def test_removed_builtin_fails_explicitly_without_replacing_output(
    name: str, tmp_path: Path
) -> None:
    from escaping.config import Settings
    from escaping.models.issue_snapshot import IssueSnapshot
    from escaping.site_compiler import SiteCompiler

    class Source:
        def get_repo(self, name: str) -> object:
            return object()

        def fetch_issue_snapshots(self, repo: object) -> list[IssueSnapshot]:
            return []

    settings = Settings.model_validate(
        {
            "github": {"repo": "owner/site", "allowed_authors": ["owner"]},
            "site": {"title": "Site", "author": "Owner", "url": "https://example.org/"},
            "theme": {"source": "builtin", "name": name},
        }
    )
    output = tmp_path / "output"
    output.mkdir()
    sentinel = output / "index.html"
    sentinel.write_text("Old output remains readable.")
    result = SiteCompiler(
        "unused", "owner/site", settings, config_root=tmp_path, github_service=Source()
    ).generate()
    assert not result.success
    assert any(
        d.code == "BUILD_FAILED" and f"built-in theme is missing: {name}" in d.message
        for d in result.diagnostics
    )
    assert list(output.iterdir()) == [sentinel]
    assert sentinel.read_text() == "Old output remains readable."
    assert not list(tmp_path.glob(".output.staging.*"))


def test_manifest_mismatch_missing_contract_and_unsafe_path_fail(
    tmp_path: Path,
) -> None:
    theme = _theme(tmp_path / "themes", "broken")
    declaration = LocalThemeConfig(name="broken", path=Path("themes/broken"))
    (theme / "theme.yaml").write_text(
        "api_version: '1'\ncapabilities: []\nrequired_templates: [base.html]\nrequired_assets: []\n",
        encoding="utf-8",
    )
    with pytest.raises(ThemeResolutionError, match="api_version"):
        ThemeLoader(tmp_path).load(declaration)

    (theme / "theme.yaml").write_text(
        "api_version: '2'\ncapabilities: []\nrequired_templates: [missing.html]\nrequired_assets: []\n",
        encoding="utf-8",
    )
    with pytest.raises(ThemeResolutionError, match=r"missing\.html"):
        ThemeLoader(tmp_path).load(declaration)

    (theme / "theme.yaml").write_text(
        "api_version: '2'\ncapabilities: []\nrequired_templates: []\nrequired_assets: []\n"
    )
    (theme / "post.html").unlink()
    with pytest.raises(ThemeResolutionError, match=r"post\.html"):
        ThemeLoader(tmp_path).load(declaration)
    (theme / "post.html").write_text("Post")

    (theme / "theme.yaml").write_text(
        "api_version: '2'\ncapabilities: []\nrequired_templates: []\nrequired_assets: [/tmp]\n",
        encoding="utf-8",
    )
    with pytest.raises(ThemeResolutionError, match="unsafe theme resource path"):
        ThemeLoader(tmp_path).load(declaration)
