from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.absolute()
_MERMAID_VERSION = "11.16.1"
_MERMAID_DIRECTORY = f"static/vendor/mermaid-{_MERMAID_VERSION}"


def test_packaging_declares_an_explicit_setuptools_backend() -> None:
    project = tomllib.loads((_PROJECT_ROOT / "pyproject.toml").read_text())

    assert project["build-system"]["build-backend"] == "setuptools.build_meta"
    assert any(
        requirement.startswith("setuptools")
        for requirement in project["build-system"]["requires"]
    )


def test_wheel_consumer_builds_site_outside_checkout(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    assert uv is not None
    uv_env = {**os.environ, "UV_CACHE_DIR": str(tmp_path / "uv-cache")}
    uv_env.pop("PYTHONPATH", None)
    uv_env.pop("PYTHONHOME", None)
    dist = tmp_path / "dist"
    subprocess.run(  # noqa: S603
        [uv, "build", "--wheel", "--out-dir", str(dist)],
        cwd=_PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=uv_env,
    )
    wheel = next(dist.glob("*.whl"))
    assert wheel.name.startswith("escpe-")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata = next(
            archive.read(name).decode("utf-8")
            for name in names
            if name.endswith(".dist-info/METADATA")
        )
        entry_points = next(
            archive.read(name).decode("utf-8")
            for name in names
            if name.endswith(".dist-info/entry_points.txt")
        )
    assert "Name: escpe\n" in metadata
    assert "Requires-Dist: nh3==0.3.7\n" in metadata
    assert any(name.endswith("/NOTICE.md") for name in names)
    assert not any(name.endswith((".so", ".dylib", ".pyd")) for name in names)
    assert "Name: escaping\n" not in metadata
    assert "Name: github-blog\n" not in metadata
    assert not any(name.startswith("github_blog/") for name in names)
    assert "escpe = escaping.cli:run_cli\n" in entry_points
    assert "blog-gen" not in entry_points
    vendor_root = f"escaping/{_MERMAID_DIRECTORY}"
    assert "escaping/static/mermaid.js" in names
    assert f"{vendor_root}/mermaid.min.js" in names
    assert f"{vendor_root}/LICENSE" in names
    assert f"{vendor_root}/README.md" in names
    assert [
        name
        for name in names
        if name.endswith(f"mermaid-{_MERMAID_VERSION}/mermaid.min.js")
    ] == [f"{vendor_root}/mermaid.min.js"]
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    script = """
import sys
from datetime import UTC, datetime
from pathlib import Path
import escaping
from escaping.config import Settings
from escaping.config import BuiltinThemeConfig
from escaping.models.issue_snapshot import IssueSnapshot
from escaping.site_compiler import SiteCompiler
from escaping.theme import ThemeLoader
assert sys.prefix != sys.base_prefix
assert Path(escaping.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())

root = Path.cwd()
settings = Settings.model_validate({
    'github': {'repo': 'owner/site', 'allowed_authors': ['owner']},
    'site': {'title': 'Consumer', 'author': 'Owner', 'url': 'https://example.com/'},
    'about': {'issue_number': 2},
    'security': {'token_env': 'TOKEN'},
})
assert settings.theme.name == 'geoqiao.me'
now = datetime(2026, 1, 1, tzinfo=UTC)
snapshots = [
    IssueSnapshot(
        1,
        'Post',
        'owner',
        '---\\nslug: post\\ndescription: A post.\\ncreated_date: "2026-01-01"\\n---\\n\\nBody.',
        ('type:blog', 'published'),
        now,
        now,
        False,
    ),
    IssueSnapshot(
        2,
        'About',
        'owner',
        '---\\ndescription: About.\\ncreated_date: "2026-01-01"\\n---\\n\\nAbout.',
        ('type:about', 'published'),
        now,
        now,
        False,
    ),
]
class FakeGitHub:
    def get_repo(self, name):
        return object()
    def fetch_issue_snapshots(self, repo):
        return snapshots

result = SiteCompiler(
    'unused',
    'owner/site',
    settings,
    config_root=root,
    github_service=FakeGitHub(),
).generate()
assert result.success, result.diagnostics
assert (root / 'output/index.html').is_file()
assert not any(path.suffix in {'.so', '.dylib', '.pyd'} for path in (root / 'output').rglob('*'))
assert (root / 'output/blog/post/index.html').is_file()
assert (root / 'output/templates/geoqiao.me/static/css/style.css').is_file()
assert (root / 'output/templates/geoqiao.me/static/js/comments.js').is_file()
home_html = (root / 'output/index.html').read_text(encoding='utf-8')
assert '<h1 id="home-title">Consumer</h1>' in home_html
assert 'class="author-mark"' not in home_html
assert 'Geo Qiao' not in home_html
assert '>GQ<' not in home_html
assert (root / 'output/templates/geoqiao.me/__MERMAID_DIRECTORY__/mermaid.min.js').is_file()
assert (root / 'output/templates/geoqiao.me/__MERMAID_DIRECTORY__/LICENSE').is_file()
for theme_name in ('Escape1', 'Escape2', 'geoqiao.me', 'Quiet'):
    theme = ThemeLoader(root).load(BuiltinThemeConfig(name=theme_name))
    destination = root / ('assets-' + theme_name)
    theme.copy_assets(destination)
    vendor = destination / 'templates' / theme_name / '__MERMAID_DIRECTORY__'
    assert (destination / 'templates' / theme_name / 'static/js/mermaid.js').is_file()
    if theme_name == 'Escape2':
        assert (destination / 'templates/Escape2/static/images/author-mark.png').is_file()
    assert (vendor / 'mermaid.min.js').is_file()
    assert (vendor / 'LICENSE').is_file()
    assert (vendor / 'README.md').is_file()
    if theme_name == 'Quiet':
        consumer_settings = settings.model_copy(update={
            'theme': BuiltinThemeConfig(name=theme_name),
            'paths': settings.paths.model_copy(update={'output': 'public'}),
        })
        result = SiteCompiler(
            'unused', 'owner/site', consumer_settings,
            config_root=root, github_service=FakeGitHub(),
        ).generate()
        assert result.success, result.diagnostics
        output = root / 'public'
        assert '<h1>Consumer</h1>' in (output / 'index.html').read_text()
        assert 'data-issue-number="1"' in (output / 'blog/post/index.html').read_text()
        for font in ('manrope-bold.ttf', 'source-serif-4.ttf', 'Manrope-OFL.txt', 'SourceSerif4-OFL.txt'):
            assert (output / 'templates' / theme_name / 'static/fonts' / font).is_file()
"""
    script = script.replace("__MERMAID_DIRECTORY__", _MERMAID_DIRECTORY)

    venv = tmp_path / "venv"
    subprocess.run(  # noqa: S603
        [uv, "venv", "--python", sys.executable, str(venv)],
        cwd=_PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=uv_env,
    )
    venv_python = venv / ("Scripts" if sys.platform == "win32" else "bin") / "python"
    subprocess.run(  # noqa: S603
        [uv, "pip", "install", "--python", str(venv_python), str(wheel)],
        cwd=_PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        env=uv_env,
    )
    subprocess.run(  # noqa: S603
        [str(venv_python), "-I", "-c", script],
        cwd=consumer,
        check=True,
        capture_output=True,
        text=True,
        env=uv_env,
    )
    subprocess.run(  # noqa: S603
        [
            str(venv_python),
            "-I",
            "-c",
            "import importlib.util, nh3; assert nh3.__version__ == '0.3.7'; assert importlib.util.find_spec('github_blog') is None",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        env=uv_env,
    )
    bin_dir = venv / ("Scripts" if sys.platform == "win32" else "bin")
    escpe = bin_dir / ("escpe.exe" if sys.platform == "win32" else "escpe")
    old_cli = bin_dir / ("blog-gen.exe" if sys.platform == "win32" else "blog-gen")
    assert escpe.is_file()
    assert not old_cli.exists()
    help_result = subprocess.run(  # noqa: S603
        [str(escpe), "--help"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        env=uv_env,
    )
    assert "usage:" in help_result.stdout.lower()

    # L2: actual installed console, with only HTTP transport replaced. Keep the
    # existing L1 full build above inside the clean wheel-installed interpreter.
    site = consumer / "nested"
    site.mkdir()
    subprocess.run(  # noqa: S603
        [
            str(venv_python),
            "-I",
            "-c",
            "import shutil; from importlib.resources import files; "
            "shutil.copytree(str(files('escaping').joinpath('themes/Quiet')), 'nested/theme')",
        ],
        cwd=consumer,
        env=uv_env,
        check=True,
        capture_output=True,
        text=True,
    )
    config = site / "config.yaml"
    config.write_text(
        "security:\n  token_env: READ_TOKEN\npaths:\n  output: public\n"
        "theme:\n  source: local\n  name: consumer-theme\n  path: theme\n"
        "projects:\n  - repository: alice/tool\n",
        encoding="utf-8",
    )
    context = consumer / "context.json"
    context.write_text(
        json.dumps(
            {
                "repository": "alice/site",
                "owner_login": "alice",
                "owner_type": "User",
                "pages_base_url": "https://notes.example/",
                "pages_base_path": "/",
            }
        ),
        encoding="utf-8",
    )
    boundary = consumer / "http-boundary"
    shutil.copytree(_PROJECT_ROOT / "tests/fixtures/cli_api", boundary)
    request_log = consumer / "requests.log"
    console_env = {
        **uv_env,
        "PYTHONPATH": str(boundary),
        "READ_TOKEN": "consumer-fixture",
        "GITHUB_ACTOR": "mallory",
        "CONSUMER_REQUEST_LOG": str(request_log),
    }
    command = [str(escpe), "--config", str(config), "--context", str(context)]
    console = subprocess.run(  # noqa: S603
        command,
        cwd=consumer,
        env=console_env,
        capture_output=True,
        text=True,
    )
    assert console.returncode == 0, console.stdout + console.stderr
    output = site / "public"
    about = (output / "about/index.html").read_text()
    assert "Alice Example" in about and "Public profile." in about
    assert "comments.js" not in about and "data-issue-number" not in about
    assert (output / "blog/128/index.html").is_file()
    assert not (output / "blog/129/index.html").exists()
    assert (output / "templates/consumer-theme/static/js/comments.js").is_file()
    projects = (output / "projects/index.html").read_text()
    assert "Renamed Tool" in projects and "Selected public project." in projects
    assert "https://github.com/alice/tool" in projects
    assert set(request_log.read_text().splitlines()) == {
        "/users/alice",
        "/repos/alice/site",
        "/repos/alice/site/issues",
        "/repos/alice/tool",
        "/repos/alice/tool/topics",
    }
    before = {
        p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()
    }
    failed = subprocess.run(  # noqa: S603
        command,
        cwd=consumer,
        env={**console_env, "CONSUMER_FAIL_ISSUES": "1"},
        capture_output=True,
        text=True,
    )
    assert failed.returncode == 1 and "FETCH_FAILED" in failed.stdout
    assert before == {
        p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()
    }
    assert (
        "consumer-fixture"
        not in console.stdout + console.stderr + failed.stdout + failed.stderr
    )
    assert all(b"consumer-fixture" not in content for content in before.values())

    # Empty Config uses the same installed console and fixed platform/API input.
    config.write_text("{}", encoding="utf-8")
    minimal = subprocess.run(  # noqa: S603
        command,
        cwd=consumer,
        env={**console_env, "GITHUB_TOKEN": "consumer-fixture"},
        capture_output=True,
        text=True,
    )
    assert minimal.returncode == 0, minimal.stdout + minimal.stderr
    assert (site / "output/blog/128/index.html").is_file()
    minimal_about = (site / "output/about/index.html").read_text()
    assert "Alice Example" in minimal_about and "comments.js" not in minimal_about
