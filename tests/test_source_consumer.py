from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).parent.parent.absolute()


@pytest.fixture
def source_consumer(tmp_path: Path) -> tuple[Path, Path, dict[str, str], list[str]]:
    source = tmp_path / "source"
    source.mkdir()
    for name in ("pyproject.toml", "uv.lock", "README.md", ".python-version"):
        shutil.copy2(_PROJECT_ROOT / name, source / name)
    shutil.copytree(
        _PROJECT_ROOT / "src",
        source / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"),
    )
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("UV_", "PYTHON")) and key != "VIRTUAL_ENV"
    }
    venv = tmp_path / "venv"
    env.update(UV_PROJECT_ENVIRONMENT=str(venv), UV_CACHE_DIR=str(tmp_path / "cache"))
    uv = shutil.which("uv")
    assert uv is not None
    command = [
        uv,
        "sync",
        "--project",
        str(source),
        "--python",
        f"{sys.version_info.major}.{sys.version_info.minor}",
        "--locked",
        "--no-default-groups",
        "--no-editable",
        "--no-build-isolation-package",
        "escpe",
    ]
    return source, venv, env, command


def test_source_consumer_uses_locked_backend_outside_checkout(
    source_consumer: tuple[Path, Path, dict[str, str], list[str]],
) -> None:
    source, venv, env, command = source_consumer
    result = subprocess.run(  # noqa: S603
        [*command, "--group", "build", "-v"],
        cwd=source.parent,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    project = tomllib.loads((source / "pyproject.toml").read_text())
    # uv does not validate PEP 518 requirements when isolation is disabled.
    assert project["dependency-groups"]["build"] == project["build-system"]["requires"]
    lock = tomllib.loads((source / "uv.lock").read_text())
    backend = next(p for p in lock["package"] if p["name"] == "setuptools")
    (source.parent / "install.log").write_text(result.stderr)
    bin_dir = venv / ("Scripts" if sys.platform == "win32" else "bin")
    script = """
import importlib.metadata as metadata
import json
import sys
from pathlib import Path
import escaping

# Check top-level distributions before setuptools exposes its vendored wheel.
assert not any(d.metadata['Name'].lower() in {'wheel', 'pytest'} for d in metadata.distributions())
import setuptools

assert sys.prefix != sys.base_prefix
for module in (escaping, setuptools):
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
distribution = metadata.distribution('escpe')
assert all(not requirement.lower().startswith(('setuptools', 'wheel')) for requirement in distribution.requires)
assert not json.loads(distribution.read_text('direct_url.json'))['dir_info'].get('editable', False)
assert metadata.version('setuptools') == sys.argv[1]
assert distribution.read_text('WHEEL').split('Generator: ')[1].splitlines()[0] == 'setuptools (' + sys.argv[1] + ')'
print(json.dumps({'python': sys.version, 'backend': metadata.version('setuptools'), 'escaping': escaping.__file__, 'wheel': distribution.read_text('WHEEL')}))
"""
    # The installed package must keep working after its source disappears.
    source.rename(source.with_name("unavailable-source"))
    installed = subprocess.run(  # noqa: S603
        [str(bin_dir / "python"), "-I", "-c", script, backend["version"]],
        cwd=source.parent,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(installed.stdout)["python"].split()[0] == sys.version.split()[0]
    console = bin_dir / ("escpe.exe" if sys.platform == "win32" else "escpe")
    help_result = subprocess.run(  # noqa: S603
        [str(console), "--help"],
        cwd=source.parent,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "usage:" in help_result.stdout.lower()
    print(installed.stdout)


@pytest.mark.parametrize("failure", ["missing-backend", "stale-lock", "bad-hash"])
def test_source_install_rejects_broken_prerequisites(
    source_consumer: tuple[Path, Path, dict[str, str], list[str]], failure: str
) -> None:
    source, venv, env, command = source_consumer
    if failure == "missing-backend":
        expected = "No module named 'setuptools'"
    else:
        command += ["--group", "build"]
        if failure == "stale-lock":
            project = source / "pyproject.toml"
            project.write_text(
                project.read_text().replace("build = [", 'build = ["packaging", ', 1)
            )
            expected = "lockfile"
        else:
            lock_path = source / "uv.lock"
            lock_text = lock_path.read_text()
            backend = next(
                p
                for p in tomllib.loads(lock_text)["package"]
                if p["name"] == "setuptools"
            )
            for wheel in backend["wheels"]:
                lock_text = lock_text.replace(wheel["hash"], "sha256:" + "0" * 64)
            lock_path.write_text(lock_text)
            expected = "Hash mismatch"
    before = (source / "uv.lock").read_bytes()
    result = subprocess.run(  # noqa: S603
        command,
        cwd=source.parent,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, result.stdout
    assert expected in result.stderr, result.stderr
    assert (source / "uv.lock").read_bytes() == before
    bin_dir = venv / ("Scripts" if sys.platform == "win32" else "bin")
    assert not (
        bin_dir / ("escpe.exe" if sys.platform == "win32" else "escpe")
    ).exists()
    (source.parent / "failure.log").write_text(result.stderr)

    if failure == "stale-lock":
        # --frozen is deliberately NOT the install contract: it ignores the new
        # build requirement instead of rejecting this mismatched source/lock.
        command[command.index("--locked")] = "--frozen"
        frozen = subprocess.run(  # noqa: S603
            command,
            cwd=source.parent,
            env=env,
            capture_output=True,
            text=True,
        )
        assert frozen.returncode == 0, frozen.stderr
        subprocess.run(  # noqa: S603
            [
                str(bin_dir / "python"),
                "-I",
                "-c",
                "import importlib.util; assert importlib.util.find_spec('packaging') is None",
            ],
            cwd=source.parent,
            env=env,
            check=True,
        )
