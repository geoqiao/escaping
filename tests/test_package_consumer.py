from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).parent.parent.absolute()
_FIXTURES = _PROJECT_ROOT / "tests/fixtures"
_TOKEN = "consumer-fixture"  # noqa: S105 - HTTP fixture credential


def test_packaging_declares_tested_pythons_and_explicit_setuptools_backend() -> None:
    project = tomllib.loads((_PROJECT_ROOT / "pyproject.toml").read_text())
    lock = tomllib.loads((_PROJECT_ROOT / "uv.lock").read_text())

    assert (_PROJECT_ROOT / ".python-version").read_text().strip() == "3.14"
    # The lowest version CI tests, and no upper bound: a cap only turns a
    # working install into a refusal when the next Python is released.
    assert project["project"]["requires-python"] == ">=3.12"
    assert lock["requires-python"] == ">=3.12"
    ci = yaml.safe_load((_PROJECT_ROOT / ".github/workflows/ci.yml").read_text())
    assert ci["jobs"]["checks"]["strategy"]["matrix"]["python-version"][0] == "3.12"
    assert project["build-system"]["build-backend"] == "setuptools.build_meta"
    assert any(
        requirement.startswith("setuptools")
        for requirement in project["build-system"]["requires"]
    )


def _issue(
    number: int, title: str, body: str, *labels: str, login: str = "owner"
) -> dict:
    return {
        "number": number,
        "title": title,
        "user": {"login": login},
        "body": body,
        "labels": [{"name": name} for name in labels],
        "created_at": f"2026-01-0{number}T00:00:00Z",
        "updated_at": f"2026-01-0{number}T00:00:00Z",
    }


def test_wheel_consumer_exports_outside_checkout(
    tmp_path: Path, source_snapshot: Path
) -> None:
    uv = shutil.which("uv")
    assert uv is not None
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("PYTHON", "GITHUB_", "CONSUMER_"))
        and key not in {"VIRTUAL_ENV", "GH_TOKEN"}
    }
    dist = tmp_path / "dist"
    # Build the wheel through an sdist, as a release is built.
    subprocess.run(  # noqa: S603
        [uv, "build", "--python", sys.executable, "--out-dir", str(dist)],
        cwd=source_snapshot,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    wheel = next(dist.glob("*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        metadata = next(
            archive.read(name).decode() for name in names if name.endswith("/METADATA")
        )
        entry_points = next(
            archive.read(name).decode()
            for name in names
            if name.endswith("/entry_points.txt")
        )
    version = tomllib.loads((_PROJECT_ROOT / "pyproject.toml").read_text())["project"][
        "version"
    ]
    assert f"Name: escaping-site\nVersion: {version}\n" in metadata
    assert "Requires-Python: >=3.12\n" in metadata
    assert "Requires-Dist: nh3==0.3.7\n" in metadata
    assert "jinja2" not in metadata.lower() and "pygments" not in metadata.lower()
    assert "escaping-site = escaping_site.cli:run_cli\n" in entry_points
    # Only Python: no Theme, template or script is shipped.
    assert all(
        name.endswith(".py") for name in names if name.startswith("escaping_site/")
    )
    assert any(name.endswith("/NOTICE.md") for name in names)
    assert not any(name.startswith("tests/") for name in names)

    venv = tmp_path / "venv"
    for command in (
        [uv, "venv", "--python", sys.executable, str(venv)],
        [uv, "pip", "install", "--python", str(venv / "bin/python"), str(wheel)],
    ):
        subprocess.run(  # noqa: S603
            command, cwd=tmp_path, check=True, capture_output=True, text=True, env=env
        )
    command_path = venv / "bin/escaping-site"

    def run(*args: str, **extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603 - installed console only
            [str(command_path), *args],
            cwd=tmp_path,
            env={**env, **extra},
            capture_output=True,
            text=True,
        )

    site = tmp_path / "site"
    site.mkdir()
    config = site / "config.json"  # JSON is valid YAML.
    config.write_text(
        json.dumps({"github": {"repo": "owner/site", "allowed_authors": ["owner"]}})
    )
    issues = site / "issues.json"
    issues.write_text(
        json.dumps(
            [
                [
                    _issue(
                        1, "Post", "Body.", "type:blog", "published", "tag:机器学习"
                    ),
                    _issue(2, "Bad tag", "Body.", "type:blog", "published", "tag:C++"),
                    _issue(3, "Idea", "Thought.", "type:idea", "published"),
                ],
                [_issue(4, "Visitor", "Spam.", "type:blog", "published", login="x")],
            ]
        )
    )
    exported = run("export", "--config", str(config), "--issues-json", str(issues))
    assert exported.returncode == 2, exported.stderr
    assert "Skipped Issues #2" in exported.stderr
    content = site / "build/content"
    assert sorted(p.relative_to(content).as_posix() for p in content.rglob("*.md")) == [
        "blog/1.md",
        "ideas/3.md",
    ]
    assert "key: 机器学习" in (content / "blog/1.md").read_text(encoding="utf-8")

    # The installed console against the GitHub API, only HTTP transport replaced.
    config.write_text("{}")
    request_log = site / "requests.log"
    api = run(
        *("export", "--config", str(config), "--output", "src/content"),
        *("--token-env", "READ_TOKEN"),
        PYTHONPATH=str(_FIXTURES / "cli_api"),
        READ_TOKEN=_TOKEN,
        GITHUB_ACTIONS="true",
        GITHUB_REPOSITORY="alice/site",
        GITHUB_ACTOR="mallory",
        CONSUMER_REQUEST_LOG=str(request_log),
    )
    assert api.returncode == 0, api.stderr
    committed = site / "src/content"
    assert (committed / "blog/128.md").is_file()
    assert not (committed / "blog/129.md").exists()  # mallory is not the owner
    assert set(request_log.read_text().splitlines()) == {
        "/repos/alice/site",
        "/repos/alice/site/issues",
    }
    assert _TOKEN not in api.stdout + api.stderr
    assert not any(
        _TOKEN.encode() in path.read_bytes()
        for path in committed.rglob("*")
        if path.is_file()
    )

    # Draft lint uses the installed wheel and needs no source or credentials.
    draft = tmp_path / "local-draft.md"
    original = b"---\r\ntitle: Draft\r\ntype: blog\r\n---\r\n\r\nBody.\r\n"
    draft.write_bytes(original)
    checked = subprocess.run(  # noqa: S603
        [str(venv / "bin/python"), "-I", "-m", "escaping_site.local_draft", str(draft)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(checked.stdout) == {
        "issue": {
            "title": "Draft",
            "labels": ["type:blog"],
            "body": "---\n{}\n---\n\r\nBody.\r\n",
        },
        "diagnostics": [],
    }
    assert draft.read_bytes() == original
