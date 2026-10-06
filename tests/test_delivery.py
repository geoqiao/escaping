"""Delivery: the reusable Action and the starter workflow, run as GitHub runs them.

Step scripts are taken from the YAML and executed with ``bash --noprofile
--norc -eo pipefail``; ``gh`` and (except in the end-to-end test) ``uv`` are
stand-ins on PATH.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

from escaping.config import read_platform_context

_ROOT = Path(__file__).parent.parent.absolute()
_STARTER = _ROOT / "starter"
_ACTION = yaml.safe_load((_ROOT / "action.yml").read_text())
_WORKFLOW = yaml.safe_load((_STARTER / ".github/workflows/pages.yml").read_text())
_TOKEN = "consumer-fixture"  # noqa: S105 - HTTP fixture credential
_BASH = shutil.which("bash") or "bash"

_FAKE_GH = r"""#!/usr/bin/env bash
# Stand-in for the GitHub CLI; answers from files under $FAKE_GH.
echo "$* token=${GH_TOKEN:+set}" >> "$FAKE_GH/calls"
if [ "$1" = api ]; then
  file="$FAKE_GH/api/$2.json"
  [ -f "$file" ] || { echo "gh: Not Found (HTTP 404)" >&2; exit 1; }
  cat "$file"
elif [ "$1 $2" = "label list" ]; then
  cat "$FAKE_GH/labels"
elif [ "$1 $2" = "label create" ]; then
  # race: another run created it first; deny: creation fails outright.
  if grep -qxF "$3" "$FAKE_GH/race"; then echo "$3" >> "$FAKE_GH/labels"; exit 1; fi
  if grep -qxF "$3" "$FAKE_GH/deny"; then exit 1; fi
  echo "$3" >> "$FAKE_GH/labels"
else
  echo "unexpected gh call: $*" >&2
  exit 64
fi
"""

_FAKE_UV = r"""#!/usr/bin/env bash
printf '%s\n' "$@" > "$FAKE_UV/args"
echo "venv=$UV_PROJECT_ENVIRONMENT token=${ESCAPING_TOKEN:+set}" > "$FAKE_UV/env"
exit "$FAKE_UV_STATUS"
"""


def _step(steps: list[dict], name: str) -> dict:
    return next(step for step in steps if step.get("name") == name)


def _run(
    step: dict, env: dict[str, str], cwd: Path
) -> subprocess.CompletedProcess[str]:
    """Run a ``bash`` step with the flags GitHub uses for ``shell: bash``."""
    script = cwd / ".step.sh"
    script.write_text(step["run"])
    try:
        return subprocess.run(  # noqa: S603 - repository step script, fake tools
            [_BASH, "--noprofile", "--norc", "-eo", "pipefail", str(script)],
            env=env,
            cwd=cwd,
            capture_output=True,
            text=True,
        )
    finally:
        script.unlink()


def _fake_tools(tmp_path: Path, **files: str) -> dict[str, str]:
    """A PATH with fake ``gh``/``uv`` in front, and their state directories."""
    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir()
    for name, body in (("gh", _FAKE_GH), ("uv", _FAKE_UV)):
        tool = bin_dir / name
        tool.write_text(body)
        tool.chmod(0o755)
    gh = tmp_path / "gh"
    for name in ("calls", "labels", "race", "deny"):
        (gh / name).parent.mkdir(parents=True, exist_ok=True)
        (gh / name).write_text(files.pop(name, ""))
    for name, body in files.items():
        (gh / "api" / name).parent.mkdir(parents=True, exist_ok=True)
        (gh / "api" / name).write_text(body)
    (tmp_path / "uv").mkdir()
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    return {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "FAKE_GH": str(gh),
        "FAKE_UV": str(tmp_path / "uv"),
        "RUNNER_TEMP": str(runner_temp),
        "GITHUB_REPOSITORY": "alice/site",
    }


def _api(pages: dict | None) -> dict[str, str]:
    repo = {"full_name": "alice/site", "owner": {"login": "alice", "type": "User"}}
    files = {"repos/alice/site.json": json.dumps(repo)}
    if pages is not None:
        files["repos/alice/site/pages.json"] = json.dumps(pages)
    return files


def test_action_and_starter_pin_code_and_scope_permissions() -> None:
    pinned = re.compile(r"[\w-]+/[\w-]+@[0-9a-f]{40}")
    assert _ACTION["runs"]["using"] == "composite"
    assert set(_ACTION["inputs"]) == {"config", "token"}
    assert set(_ACTION["outputs"]) == {"output", "skipped-issues"}
    for step in _ACTION["runs"]["steps"]:
        if "uses" in step:
            assert pinned.fullmatch(step["uses"]), step["uses"]
        else:
            # Inputs reach scripts only through env, never by interpolation.
            assert step["shell"] == "bash" and "${{" not in step["run"]
    build = _step(_ACTION["runs"]["steps"], "Build the site")
    assert build["id"] == "build"
    assert build["env"]["ESCAPING_TOKEN"] == "${{ inputs.token }}"  # noqa: S105 - Actions expression

    workflow = _WORKFLOW
    assert workflow["permissions"] == {}
    assert workflow["concurrency"] == {
        "group": "pages-${{ github.ref }}",
        "cancel-in-progress": False,
    }
    jobs = workflow["jobs"]
    assert {name: job["permissions"] for name, job in jobs.items()} == {
        "labels": {"issues": "write"},
        "build": {"contents": "read", "issues": "read", "pages": "read"},
        "deploy": {"pages": "write", "id-token": "write"},
    }
    assert (
        "default_branch" in jobs["labels"]["if"] and jobs["deploy"]["needs"] == "build"
    )
    assert jobs["build"]["if"] == jobs["labels"]["if"]
    version = tomllib.loads((_ROOT / "pyproject.toml").read_text())["project"][
        "version"
    ]
    for job in jobs.values():
        for step in job["steps"]:
            assert "continue-on-error" not in step
            if "run" in step:
                assert "${{" not in step["run"]
            uses = step.get("uses", "")
            if uses.startswith("geoqiao/escaping@"):
                assert uses == f"geoqiao/escaping@v{version}"
            elif uses:
                assert pinned.fullmatch(uses), uses
            if uses.startswith("actions/checkout@"):
                assert step["with"]["persist-credentials"] is False
    upload = jobs["build"]["steps"][-1]
    assert upload["with"]["path"] == "${{ steps.site.outputs.output }}"
    assert yaml.safe_load((_STARTER / "config.yaml").read_text()) == {}
    template = (_STARTER / ".github/ISSUE_TEMPLATE/write.md").read_text()
    assert "labels" not in yaml.safe_load(template.split("---")[1])


@pytest.mark.parametrize(
    "pages",
    [
        {"html_url": "https://notes.example/", "build_type": "workflow"},
        None,  # Pages not enabled
        {"html_url": "https://alice.github.io/", "build_type": "legacy"},
    ],
    ids=["actions-pages", "no-pages", "branch-pages"],
)
def test_context_step_reads_repository_and_requires_actions_pages(
    tmp_path: Path, pages: dict | None
) -> None:
    env = _fake_tools(tmp_path, **_api(pages))
    env["GH_TOKEN"] = _TOKEN
    step = _step(_ACTION["runs"]["steps"], "Read the repository and Pages settings")
    result = _run(step, env, tmp_path)
    context = Path(env["RUNNER_TEMP"]) / "escaping-context.json"
    calls = Path(env["FAKE_GH"], "calls").read_text()
    assert _TOKEN not in result.stdout + result.stderr + calls
    assert "token=set" in calls
    if pages is None or pages["build_type"] != "workflow":
        assert result.returncode == 1 and not context.exists()
        assert "::error title=GitHub Pages::" in result.stdout
        assert "Source to GitHub Actions" in result.stdout
        return
    assert result.returncode == 0, result.stderr
    platform = read_platform_context(context)
    assert platform.repository == "alice/site" and platform.owner_login == "alice"
    assert platform.owner_type == "User"
    assert str(platform.pages_base_url) == "https://notes.example/"


@pytest.mark.parametrize(("status", "expected"), [(0, 0), (2, 0), (1, 1)])
def test_build_step_passes_inputs_as_arguments_and_maps_skipped_to_success(
    tmp_path: Path, status: int, expected: int
) -> None:
    env = _fake_tools(tmp_path)
    runner_temp = env["RUNNER_TEMP"]
    env.update(
        FAKE_UV_STATUS=str(status),
        GITHUB_ACTION_PATH="/actions/escaping",
        ESCAPING_CONFIG="my site/config.yaml",
        ESCAPING_TOKEN=_TOKEN,
        UV_PROJECT_ENVIRONMENT=f"{runner_temp}/escaping-venv",
    )
    result = _run(_step(_ACTION["runs"]["steps"], "Build the site"), env, tmp_path)
    assert result.returncode == expected, result.stderr
    args = Path(env["FAKE_UV"], "args").read_text().splitlines()
    assert args == [
        "run",
        "--project",
        "/actions/escaping",
        "--locked",
        "--python",
        "3.14",
        "--no-default-groups",
        "--group",
        "build",
        "--no-build-isolation-package",
        "escpe",
        "escpe",
        "build",
        "--config",
        "my site/config.yaml",
        "--context",
        f"{runner_temp}/escaping-context.json",
        "--token-env",
        "ESCAPING_TOKEN",
    ]
    assert Path(env["FAKE_UV"], "env").read_text() == (
        f"venv={runner_temp}/escaping-venv token=set\n"
    )


def test_release_publishes_the_tagged_version_without_a_stored_token() -> None:
    release = yaml.safe_load((_ROOT / ".github/workflows/release.yml").read_text())
    # PyYAML's YAML 1.1 loader reads the unquoted Actions `on` key as True.
    assert release[True] == {"push": {"tags": ["v*"]}}
    assert release["permissions"] == {}
    build, publish = release["jobs"]["build"], release["jobs"]["publish"]
    pinned = re.compile(r"[\w-]+/[\w-]+@[0-9a-f]{40}")
    for step in (*build["steps"], *publish["steps"]):
        assert "uses" not in step or pinned.fullmatch(step["uses"])
    # Only the job that runs no project code can ask PyPI for credentials.
    assert build["permissions"] == {"contents": "read"}
    assert publish["permissions"] == {"id-token": "write"}
    assert publish["needs"] == "build" and publish["environment"]["name"] == "pypi"
    assert not any("checkout" in step.get("uses", "") for step in publish["steps"])
    assert (
        'if [ "$TAG" != "v$version" ]'
        in _step(build["steps"], "Check that the tag is the package version")["run"]
    )
    text = (_ROOT / ".github/workflows/release.yml").read_text()
    assert "secrets." not in text and "password" not in text


def test_label_job_creates_only_missing_labels_and_tolerates_races(
    tmp_path: Path,
) -> None:
    step = _step(
        _WORKFLOW["jobs"]["labels"]["steps"], "Create missing publishing labels"
    )
    env = _fake_tools(tmp_path, labels="Published\nbug\n", race="type:idea\n")
    env["GITHUB_STEP_SUMMARY"] = str(tmp_path / "summary.md")
    result = _run(step, env, tmp_path)
    assert result.returncode == 0, result.stderr
    labels = Path(env["FAKE_GH"], "labels").read_text().splitlines()
    assert labels == ["Published", "bug", "type:blog", "type:idea", "type:about"]
    assert "Publishing labels are ready" in (tmp_path / "summary.md").read_text()

    (tmp_path / "denied").mkdir()
    denied = _fake_tools(tmp_path / "denied", deny="type:blog\n")
    denied["GITHUB_STEP_SUMMARY"] = str(tmp_path / "denied-summary.md")
    result = _run(step, denied, tmp_path / "denied")
    assert result.returncode != 0
    assert not (tmp_path / "denied-summary.md").exists()


def test_action_builds_the_starter_site_end_to_end(
    tmp_path: Path, source_snapshot: Path
) -> None:
    """Real uv installs this checkout as the Action and builds via the HTTP fixture."""
    uv = shutil.which("uv")
    assert uv and shutil.which("jq")
    site = tmp_path / "site"
    shutil.copytree(_STARTER, site)
    fakes = _fake_tools(
        tmp_path,
        **_api({"html_url": "https://notes.example/", "build_type": "workflow"}),
    )
    # A clean runner-like environment: nothing from the outer uv, pytest or CI job.
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("UV_", "PYTHON", "GITHUB_", "RUNNER_", "CONSUMER_"))
        and key not in {"VIRTUAL_ENV", "GH_TOKEN", "GITHUB_TOKEN"}
    }
    if "UV_CACHE_DIR" in os.environ:
        env["UV_CACHE_DIR"] = os.environ["UV_CACHE_DIR"]
    runner_temp = fakes["RUNNER_TEMP"]
    output_file, summary = tmp_path / "github-output", tmp_path / "summary.md"
    request_log = tmp_path / "requests.log"
    env.update(
        PATH=f"{Path(uv).parent}{os.pathsep}{env['PATH']}",
        FAKE_GH=fakes["FAKE_GH"],
        RUNNER_TEMP=runner_temp,
        GITHUB_REPOSITORY="alice/site",
        GITHUB_ACTIONS="true",
        GITHUB_ACTOR="mallory",
        GITHUB_ACTION_PATH=str(source_snapshot),
        GITHUB_OUTPUT=str(output_file),
        GITHUB_STEP_SUMMARY=str(summary),
        GH_TOKEN=_TOKEN,
        ESCAPING_CONFIG="config.yaml",
        ESCAPING_TOKEN=_TOKEN,
        UV_PROJECT_ENVIRONMENT=f"{runner_temp}/escaping-venv",
        PYTHONPATH=str(_ROOT / "tests/fixtures/cli_api"),
        CONSUMER_REQUEST_LOG=str(request_log),
    )
    steps = _ACTION["runs"]["steps"]
    context_env = {**env, "PATH": fakes["PATH"]}
    context = _run(
        _step(steps, "Read the repository and Pages settings"), context_env, site
    )
    assert context.returncode == 0, context.stderr
    built = _run(_step(steps, "Build the site"), env, site)
    assert built.returncode == 0, built.stdout + built.stderr

    output = site / "output"
    assert output_file.read_text() == f"output={output}\nskipped-issues=\n"
    assert (output / ".escaping-output").is_file()
    post = (output / "blog/128/index.html").read_text()
    assert '<link rel="canonical" href="https://notes.example/blog/128/"' in post
    assert not (output / "blog/129").exists()  # mallory is not an allowed author
    assert "Public profile." in (output / "about/index.html").read_text()
    assert (output / "assets/css/style.css").is_file()
    assert (output / "assets/escaping/mermaid/mermaid.min.js").is_file()
    assert "Published output/." in summary.read_text()
    assert request_log.read_text().splitlines().count("/users/alice") == 1

    before = {p: p.read_bytes() for p in output.rglob("*") if p.is_file()}
    output_file.write_text("")
    failed = _run(
        _step(steps, "Build the site"), {**env, "CONSUMER_FAIL_ISSUES": "1"}, site
    )
    assert failed.returncode == 1
    assert "::error title=FETCH_FAILED::" in failed.stdout
    assert output_file.read_text() == ""
    assert before == {p: p.read_bytes() for p in output.rglob("*") if p.is_file()}

    logs = context.stdout + context.stderr + built.stdout + built.stderr
    logs += failed.stdout + failed.stderr + summary.read_text()
    assert _TOKEN not in logs
    assert all(_TOKEN.encode() not in body for body in before.values())
