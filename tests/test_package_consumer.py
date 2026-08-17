from __future__ import annotations

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
sys.path.insert(0, __WHEEL__)
import escaping
from escaping.config import Settings
from escaping.config import BuiltinThemeConfig
from escaping.models.issue_snapshot import IssueSnapshot
from escaping.site_compiler import SiteCompiler
from escaping.theme import ThemeLoader
assert '.whl/' in escaping.__file__.replace('\\\\', '/')

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
assert (root / 'output/blog/post/index.html').is_file()
assert (root / 'output/templates/geoqiao.me/static/css/style.css').is_file()
assert (root / 'output/templates/geoqiao.me/static/js/comments.js').is_file()
home_html = (root / 'output/index.html').read_text(encoding='utf-8')
assert 'aria-label="Owner author mark"' in home_html
assert 'Geo Qiao' not in home_html
assert '>GQ<' not in home_html
assert (root / 'output/templates/geoqiao.me/__MERMAID_DIRECTORY__/mermaid.min.js').is_file()
assert (root / 'output/templates/geoqiao.me/__MERMAID_DIRECTORY__/LICENSE').is_file()
for theme_name in ('Escape1', 'Escape2', 'geoqiao.me'):
    theme = ThemeLoader(root).load(BuiltinThemeConfig(name=theme_name))
    destination = root / ('assets-' + theme_name)
    theme.copy_assets(destination)
    vendor = destination / 'templates' / theme_name / '__MERMAID_DIRECTORY__'
    assert (destination / 'templates' / theme_name / 'static/js/mermaid.js').is_file()
    assert (vendor / 'mermaid.min.js').is_file()
    assert (vendor / 'LICENSE').is_file()
    assert (vendor / 'README.md').is_file()
""".replace("__WHEEL__", repr(str(wheel)))
    script = script.replace("__MERMAID_DIRECTORY__", _MERMAID_DIRECTORY)
    subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        cwd=consumer,
        check=True,
        capture_output=True,
        text=True,
        env=uv_env,
    )

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
        [
            str(venv_python),
            "-c",
            "import importlib.util; assert importlib.util.find_spec('github_blog') is None",
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
