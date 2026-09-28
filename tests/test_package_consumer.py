from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent.absolute()
_FIXTURES = _PROJECT_ROOT / "tests/fixtures"
_TOKEN = "consumer-fixture"  # noqa: S105 - HTTP fixture credential


def test_packaging_declares_python_314_only_and_explicit_setuptools_backend() -> None:
    project = tomllib.loads((_PROJECT_ROOT / "pyproject.toml").read_text())
    lock = tomllib.loads((_PROJECT_ROOT / "uv.lock").read_text())

    assert (_PROJECT_ROOT / ".python-version").read_text().strip() == "3.14"
    assert project["project"]["requires-python"] == ">=3.14,<3.15"
    assert lock["requires-python"] == "==3.14.*"
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


def test_wheel_consumer_builds_site_outside_checkout(
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
    assert f"Name: escpe\nVersion: {version}\n" in metadata
    assert "Requires-Python: <3.15,>=3.14\n" in metadata
    assert "Requires-Dist: nh3==0.3.7\n" in metadata
    assert "Requires-Dist: pygments==2.19.2\n" in metadata
    assert "escpe = escaping.cli:run_cli\n" in entry_points
    assert {n.split("/")[2] for n in names if n.startswith("escaping/themes/")} == {
        "quiet"
    }
    assert {
        "escaping/themes/quiet/theme.yaml",
        "escaping/themes/quiet/404.html",
        "escaping/themes/quiet/static/css/syntax.css",
        "escaping/static/comments.js",
        "escaping/static/mermaid.js",
        "escaping/static/mermaid/mermaid.min.js",
        "escaping/static/mermaid/LICENSE",
    } <= names
    assert any(name.endswith("/NOTICE.md") for name in names)
    assert not any(name.endswith((".so", ".dylib", ".pyd")) for name in names)
    assert not any(name.startswith(("tests/", "starter/")) for name in names)

    venv = tmp_path / "venv"
    for command in (
        [uv, "venv", "--python", sys.executable, str(venv)],
        [uv, "pip", "install", "--python", str(venv / "bin/python"), str(wheel)],
    ):
        subprocess.run(  # noqa: S603
            command, cwd=tmp_path, check=True, capture_output=True, text=True, env=env
        )
    escpe = venv / "bin/escpe"

    def run(*args: str, **extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603 - installed console only
            [str(escpe), *args],
            cwd=tmp_path,
            env={**env, **extra},
            capture_output=True,
            text=True,
        )

    # A site outside the checkout: an extending and an independent local Theme.
    site = tmp_path / "site"
    site.mkdir()
    shutil.copytree(_FIXTURES / "extends_theme", site / "child")
    shutil.copytree(_FIXTURES / "independent_theme", site / "theme")
    identity = {
        "github": {"repo": "owner/site", "allowed_authors": ["owner"]},
        "site": {
            "title": "Consumer",
            "author": "Owner",
            "description": "Notes.",
            "url": "https://example.com/",
            "language": "zh-CN",
        },
        "profile": {"avatar": "", "bio": "Profile bio."},
        "projects": [
            {
                "website": "https://tool.example/",
                "slug": "tool",
                "title": "Tool",
                "summary": "A tool.",
            }
        ],
    }
    child = site / "child.json"  # JSON is valid YAML.
    pages = {
        "extra": [
            {"path": "/now/", "template": "now.html"},
            {
                "path": "/projects/{slug}/",
                "template": "project.html",
                "for_each": "projects",
            },
        ]
    }
    child.write_text(
        json.dumps({**identity, "pages": pages, "theme": {"use": "./child"}})
    )
    independent = site / "independent.json"
    independent.write_text(json.dumps({**identity, "theme": {"use": "./theme"}}))
    for config in (child, independent):
        checked = run("theme", "check", "--config", str(config))
        assert checked.returncode == 0, checked.stderr

    issues = site / "issues.json"
    code = '```python\nprint("hello")\n```\n\n```mermaid\ngraph LR\nA-->B\n```'
    issues.write_text(
        json.dumps(
            [
                [
                    _issue(1, "Post", code, "type:blog", "published", "tag:机器学习"),
                    _issue(2, "Bad tag", "Body.", "type:blog", "published", "tag:C++"),
                    _issue(3, "Idea", "Thought.", "type:idea", "published"),
                ],
                [_issue(4, "Visitor", "Spam.", "type:blog", "published", login="x")],
            ]
        )
    )
    built = run("build", "--config", str(child), "--issues-json", str(issues))
    assert built.returncode == 2, built.stderr
    assert "Skipped Issues #2" in built.stderr
    output = site / "output"
    assert (output / ".escaping-output").is_file()
    assert not (output / "blog/2").exists() and not (output / "blog/4").exists()
    post = (output / "blog/1/index.html").read_text()
    code_classes = re.search(r'<code class="([^"]+)">', post)
    assert code_classes and set(code_classes[1].split()) == {
        "syntax",
        "language-python",
    }
    assert "<span class=" in post and 'href="/assets/css/syntax.css"' in post
    assert '<meta name="x-now" content="Working on escaping.">' in post
    assert (
        'lang="zh-CN"' in post and "/tags/%E6%9C%BA%E5%99%A8%E5%AD%A6%E4%B9%A0/" in post
    )
    assert (output / "tags/机器学习/index.html").is_file()
    assert "现在" in (output / "now/index.html").read_text()
    assert (output / "projects/tool/index.html").is_file()
    for asset in (
        "assets/css/style.css",  # from Quiet
        "assets/css/extra.css",  # from the child Theme
        "assets/fonts/source-serif-4.ttf",
        "assets/escaping/mermaid/mermaid.min.js",
        "404.html",
    ):
        assert (output / asset).is_file(), asset

    # The installed console against the GitHub API, only HTTP transport replaced.
    context = site / "context.json"
    context.write_text(
        json.dumps(
            {
                "repository": "alice/site",
                "owner_login": "alice",
                "owner_type": "User",
                "pages_base_url": "https://notes.example/",
            }
        )
    )
    independent.write_text(
        json.dumps(
            {
                "theme": {"use": "./theme", "options": {"footer_note": "Bye."}},
                "projects": [{"repository": "alice/tool"}],
                "paths": {"output": "public"},
            }
        )
    )
    request_log = site / "requests.log"
    api = run(
        *("build", "--config", str(independent), "--context", str(context)),
        *("--token-env", "READ_TOKEN"),
        PYTHONPATH=str(_FIXTURES / "cli_api"),
        READ_TOKEN=_TOKEN,
        GITHUB_ACTOR="mallory",
        CONSUMER_REQUEST_LOG=str(request_log),
    )
    assert api.returncode == 0, api.stderr
    public = site / "public"
    about = (public / "about/index.html").read_text()
    assert "Alice Example" in about and "Public profile." in about
    assert (public / "blog/128/index.html").is_file()
    assert not (public / "blog/129").exists()  # mallory is not the owner
    assert "Bye." in (public / "blog/128/index.html").read_text()
    projects = (public / "projects/index.html").read_text()
    assert "Renamed Tool" in projects and "Selected public project." in projects
    assert (public / "assets/js/site.js").is_file()
    assert set(request_log.read_text().splitlines()) == {
        "/users/alice",
        "/repos/alice/site",
        "/repos/alice/site/issues",
        "/repos/alice/tool",
        "/repos/alice/tool/topics",
    }
    assert _TOKEN not in api.stdout + api.stderr
    assert not any(
        _TOKEN.encode() in path.read_bytes()
        for path in public.rglob("*")
        if path.is_file()
    )

    # Draft lint uses the installed wheel and needs no source or credentials.
    draft = tmp_path / "local-draft.md"
    original = b"---\r\ntitle: Draft\r\ntype: blog\r\n---\r\n\r\nBody.\r\n"
    draft.write_bytes(original)
    checked = subprocess.run(  # noqa: S603
        [str(venv / "bin/python"), "-I", "-m", "escaping.local_draft", str(draft)],
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
