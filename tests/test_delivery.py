from __future__ import annotations

import copy
import io
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import threading
from email.message import Message
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import unquote, urlsplit
from urllib.request import Request, build_opener

import pytest
import yaml

_ROOT = Path(__file__).parent.parent.absolute()
_STARTER = _ROOT / "starter"
_SCRIPTS = _STARTER / ".github/scripts"
_API = "https://api.github.com/repos/geoqiao/escaping"
_COMMIT = "a" * 40
_TAG = "b" * 40
_REPOSITORY = "alice/site"


def release_responses(commit: str = _COMMIT, version: str = "v1.0.0") -> dict:
    return {
        _API + "/releases/latest": {
            "id": 7,
            "url": _API + "/releases/7",
            "draft": False,
            "prerelease": False,
            "published_at": "2026-01-01T00:00:00Z",
            "tag_name": version,
            "target_commitish": "main",
            "immutable": True,
        },
        _API + "/git/ref/tags/" + version: {
            "ref": "refs/tags/" + version,
            "url": _API + "/git/refs/tags/" + version,
            "object": {
                "type": "commit",
                "sha": commit,
                "url": _API + "/git/commits/" + commit,
            },
        },
        _API + "/git/commits/" + commit: {
            "sha": commit,
            "url": _API + "/git/commits/" + commit,
        },
        _API + "/commits/" + commit: {
            "sha": commit,
            "url": _API + "/commits/" + commit,
        },
    }


@pytest.fixture
def api_transport(monkeypatch: pytest.MonkeyPatch) -> tuple[dict, list]:
    responses: dict = {}
    calls: list = []

    class Response(io.BytesIO):
        status: int = 200

    def open_request(request: Request, timeout: int) -> io.BytesIO:
        assert urlsplit(request.full_url).hostname == "api.github.com"
        token = "label-fixture" if "/labels" in request.full_url else "platform-fixture"
        assert request.get_header("Authorization") == "Bearer " + token
        assert timeout == 30
        calls.append((request.get_method(), request.full_url, request.data))
        value = responses[request.full_url]
        if callable(value):
            value = value(request)
        if isinstance(value, int) and value >= 300:
            raise HTTPError(
                request.full_url, value, "private API body", Message(), None
            )
        result = Response(json.dumps(value).encode())
        result.status = value if isinstance(value, int) else 200
        return result

    monkeypatch.setattr(
        "urllib.request.build_opener", lambda *args: SimpleNamespace(open=open_request)
    )
    monkeypatch.setenv("PLATFORM_TOKEN", "platform-fixture")
    monkeypatch.setenv("GITHUB_REPOSITORY", _REPOSITORY)
    return responses, calls


def run_platform(
    command: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    selection: str = "stable",
) -> dict:
    monkeypatch.setenv("ESCAPING_VERSION", selection)
    monkeypatch.setattr("sys.argv", ["github_platform.py", command])
    runpy.run_path(str(_SCRIPTS / "github_platform.py"), run_name="__main__")
    return json.loads(capsys.readouterr().out)


def test_version_selection_is_run_local_and_fixed_identity(
    api_transport: tuple[dict, list],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    responses, calls = api_transport
    responses.update(release_responses())
    first = run_platform("version", monkeypatch, capsys)
    assert first["commit"] == _COMMIT
    assert sum(url.endswith("/releases/latest") for _, url, _ in calls) == 1
    responses.update(release_responses("c" * 40, "v2.0.0"))
    second = run_platform("version", monkeypatch, capsys)
    assert second["commit"] == "c" * 40 and first["commit"] == _COMMIT

    calls.clear()
    assert run_platform("version", monkeypatch, capsys, _COMMIT)["commit"] == _COMMIT
    assert calls == [("GET", _API + "/commits/" + _COMMIT, None)]
    responses[_API + "/releases/tags/v1.0.0"] = release_responses()[
        _API + "/releases/latest"
    ]
    responses[_API + "/git/ref/tags/v1.0.0"]["object"] = {
        "type": "tag",
        "sha": _TAG,
        "url": _API + "/git/tags/" + _TAG,
    }
    responses[_API + "/git/tags/" + _TAG] = {
        "sha": _TAG,
        "url": _API + "/git/tags/" + _TAG,
        "object": {
            "type": "commit",
            "sha": _COMMIT,
            "url": _API + "/git/commits/" + _COMMIT,
        },
    }
    calls.clear()
    assert run_platform("version", monkeypatch, capsys, "v1.0.0")["commit"] == _COMMIT
    assert not any(url.endswith("/latest") for _, url, _ in calls)


@pytest.mark.parametrize(
    "failure",
    [
        "prerelease",
        "draft",
        "foreign-release",
        "foreign-object",
        "wrong-ref",
        "cycle",
        "depth",
        "mutable-tag",
        "missing-release",
        "http-error",
    ],
)
def test_version_failures_never_fall_back(
    failure: str,
    api_transport: tuple[dict, list],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    responses, calls = api_transport
    responses.update(release_responses())
    release = responses[_API + "/releases/latest"]
    reference = responses[_API + "/git/ref/tags/v1.0.0"]
    selection = "stable"
    if failure in {"prerelease", "draft"}:
        release[failure] = True
    elif failure == "foreign-release":
        release["url"] = "https://evil.example/releases/7"
    elif failure == "foreign-object":
        reference["object"]["url"] = "https://evil.example/commit"
    elif failure == "wrong-ref":
        reference["ref"] = "refs/heads/main"
    elif failure in {"cycle", "depth"}:
        target = {"type": "tag", "sha": _TAG, "url": _API + "/git/tags/" + _TAG}
        reference["object"] = target
        for index in range(9):
            following = {
                "type": "tag",
                "sha": f"{index:040x}",
                "url": _API + f"/git/tags/{index:040x}",
            }
            responses[target["url"]] = {
                **target,
                "object": target if failure == "cycle" else following,
            }
            target = following
    elif failure == "mutable-tag":
        selection = "v1.0.0"
        release["immutable"] = False
        responses[_API + "/releases/tags/v1.0.0"] = release
    else:
        responses[_API + "/releases/latest"] = (
            404 if failure == "missing-release" else 503
        )
    with pytest.raises(SystemExit) as error:
        run_platform("version", monkeypatch, capsys, selection)
    assert error.value.code == 1
    output = capsys.readouterr()
    assert not output.out
    assert "platform-fixture" not in output.err and "private API body" not in output.err
    assert all(
        method == "GET" and not url.endswith("/commits/main")
        for method, url, _ in calls
    )
    assert len(calls) <= 10


def test_context_is_trusted_pages_root_even_when_config_could_override_it(
    api_transport: tuple[dict, list],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    responses, calls = api_transport
    prefix = "https://api.github.com/repos/" + _REPOSITORY
    responses[prefix] = {
        "full_name": _REPOSITORY,
        "owner": {"login": "alice", "type": "User"},
    }
    responses[prefix + "/pages"] = {
        "html_url": "https://notes.example/",
        "build_type": "workflow",
    }
    monkeypatch.setenv("GITHUB_ACTOR", "mallory")
    context = run_platform("context", monkeypatch, capsys)
    assert context == {
        "repository": _REPOSITORY,
        "owner_login": "alice",
        "owner_type": "User",
        "pages_base_url": "https://notes.example/",
        "pages_base_path": "/",
    }
    for patch in (
        {"html_url": "https://notes.example/project/"},
        {"html_url": "http://notes.example/"},
        {"html_url": "https://user@notes.example/"},
        {"html_url": "https://notes.example/?x=1"},
        {"build_type": "legacy"},
    ):
        original = responses[prefix + "/pages"]
        responses[prefix + "/pages"] = {**original, **patch}
        with pytest.raises(SystemExit):
            run_platform("context", monkeypatch, capsys)
        capsys.readouterr()
        responses[prefix + "/pages"] = original
    responses[prefix]["owner"]["login"] = "mallory"
    with pytest.raises(SystemExit):
        run_platform("context", monkeypatch, capsys)
    capsys.readouterr()
    assert all(method == "GET" for method, _, _ in calls)


def test_inline_label_initializer_preserves_user_labels_and_verifies_races(
    api_transport: tuple[dict, list], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    responses, calls = api_transport
    workflow = yaml.safe_load((_STARTER / ".github/workflows/pages.yml").read_text())
    script = workflow["jobs"]["labels"]["steps"][0]["run"]
    state = {
        "published": {
            "name": "published",
            "color": "abcdef",
            "description": "User-owned",
        }
    }
    before = copy.deepcopy(state["published"])
    prefix = "https://api.github.com/repos/" + _REPOSITORY
    mode = "create"

    def transport(request: Request) -> int:
        name = unquote(request.full_url.rsplit("/", 1)[-1])
        if request.get_method() == "GET":
            return 200 if name in state else 404
        assert request.get_method() == "POST" and request.full_url == prefix + "/labels"
        assert isinstance(request.data, bytes)
        data = json.loads(request.data)
        if mode != "failed-race":
            state[data["name"]] = data
        return 201 if mode == "create" else 422

    for name in ("published", "type:blog", "type:idea", "type:about"):
        responses[prefix + "/labels/" + name.replace(":", "%3A")] = transport
    responses[prefix + "/labels"] = transport
    monkeypatch.setenv("LABEL_TOKEN", "label-fixture")
    summary = tmp_path / "summary"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    for _ in range(2):
        exec(compile(script, "pages.yml:labels", "exec"), {"__name__": "__main__"})  # noqa: S102 - checked-in canonical workflow only
    assert state["published"] == before
    assert set(state) == {"published", "type:blog", "type:idea", "type:about"}
    assert sum(method == "POST" for method, _, _ in calls) == 3
    assert "Refresh" in summary.read_text()
    state.pop("type:blog")
    mode = "race"
    exec(compile(script, "pages.yml:labels", "exec"), {"__name__": "__main__"})  # noqa: S102
    state.pop("type:blog")
    mode = "failed-race"
    before_summary = summary.read_bytes()
    with pytest.raises(SystemExit):
        exec(compile(script, "pages.yml:labels", "exec"), {"__name__": "__main__"})  # noqa: S102
    assert summary.read_bytes() == before_summary
    responses[prefix + "/labels/published"] = 403
    with pytest.raises(SystemExit):
        exec(compile(script, "pages.yml:labels", "exec"), {"__name__": "__main__"})  # noqa: S102
    assert summary.read_bytes() == before_summary


def test_http_redirects_do_not_forward_platform_or_label_credentials(
    api_transport: tuple[dict, list], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    responses, _ = api_transport
    for name in ("published", "type:blog", "type:idea", "type:about"):
        responses[
            "https://api.github.com/repos/"
            + _REPOSITORY
            + "/labels/"
            + name.replace(":", "%3A")
        ] = 200
    monkeypatch.setenv("LABEL_TOKEN", "label-fixture")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary"))
    workflow = yaml.safe_load((_STARTER / ".github/workflows/pages.yml").read_text())
    labels: dict = {"__name__": "__main__"}
    exec(  # noqa: S102 - checked-in canonical workflow only
        compile(
            workflow["jobs"]["labels"]["steps"][0]["run"], "pages.yml:labels", "exec"
        ),
        labels,
    )
    platform = runpy.run_path(str(_SCRIPTS / "github_platform.py"))
    received: list[str] = []

    class Redirect(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            received.append(self.path)
            self.send_response(302)
            self.send_header("Location", "/credential-sink")
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass

    with HTTPServer(("127.0.0.1", 0), Redirect) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for namespace in (platform, labels):
                request = Request(
                    f"http://127.0.0.1:{server.server_port}/start",
                    headers={"Authorization": "Bearer redirect-fixture"},
                )
                with pytest.raises(HTTPError) as error:
                    build_opener(namespace["NoRedirect"]).open(request, timeout=3)
                assert error.value.code == 302
        finally:
            server.shutdown()
            thread.join()
    assert received == ["/start", "/start"]


def test_token_mapping_rejects_startup_controls_and_existing_names() -> None:
    adapter = runpy.run_path(str(_SCRIPTS / "run_configured.py"))
    inherited = {
        "PATH": "/bin",
        "COMPILER_TOKEN": "fixture",
        "PLATFORM_TOKEN": "other",
        "LABEL_TOKEN": "labels",
        "GH_TOKEN": "gh",
        "GITHUB_TOKEN": "old",
    }
    mapped = adapter["compiler_env"]("READ_TOKEN", "fixture", inherited)
    assert mapped == {"PATH": "/bin", "READ_TOKEN": "fixture"}
    assert adapter["compiler_env"]("GITHUB_TOKEN", "fixture", inherited) == {
        "PATH": "/bin",
        "GITHUB_TOKEN": "fixture",
    }
    for name in (
        "PATH",
        "HOME",
        "PYTHONPATH",
        "pythonwarnings",
        "LD_PRELOAD",
        "DYLD_INSERT_LIBRARIES",
        "BASH_ENV",
        "ENV",
        "IFS",
        "GIT_CONFIG_COUNT",
        "UV_INDEX",
        "GITHUB_OUTPUT",
        "RUNNER_TEMP",
        "NODE_OPTIONS",
        "HTTPS_PROXY",
        "SSLKEYLOGFILE",
        "OPENSSL_CONF",
        "OPENSSL_MODULES",
        "CUSTOM",
    ):
        with pytest.raises(ValueError):
            adapter["compiler_env"](name, "fixture", {"CUSTOM": "existing"})


def test_workflow_uses_only_reviewed_code_and_separates_permissions() -> None:
    text = (_STARTER / ".github/workflows/pages.yml").read_text()
    workflow = yaml.safe_load(text)
    assert set(workflow["on"]) == {"issues", "push", "workflow_dispatch"}
    assert workflow["on"]["push"] is None
    assert {"opened", "edited", "labeled", "unlabeled"} <= set(
        workflow["on"]["issues"]["types"]
    )
    assert workflow["permissions"] == {}
    assert "github.ref" in workflow["concurrency"]["group"]
    assert workflow["concurrency"]["cancel-in-progress"] is False
    jobs = workflow["jobs"]
    assert {name: job["permissions"] for name, job in jobs.items()} == {
        "labels": {"issues": "write"},
        "context": {"contents": "read", "pages": "read"},
        "build": {"contents": "read", "issues": "read"},
        "deploy": {"pages": "write", "id-token": "write"},
    }
    assert jobs["build"]["needs"] == ["labels", "context"]
    assert jobs["deploy"]["needs"] == "build"
    assert (
        len(jobs["labels"]["steps"]) == 1 and "uses" not in jobs["labels"]["steps"][0]
    )
    assert ".github/scripts" not in jobs["labels"]["steps"][0]["run"]
    for job in jobs.values():
        assert "repository.default_branch" in job["if"]
        for step in job["steps"]:
            assert "continue-on-error" not in step
            if "uses" in step:
                assert re.fullmatch(r"[\w/-]+@[0-9a-f]{40}", step["uses"])
                if step["uses"].startswith("actions/checkout@"):
                    assert step["with"]["persist-credentials"] is False
                    assert step["with"]["ref"] in {
                        "${{ github.sha }}",
                        "${{ steps.version.outputs.sha }}",
                    }
    assert "github.event.issue." not in text and "configure-pages" not in text
    assert "render_slug_redirects" not in text and "build-requirements.txt" not in text
    build_steps = jobs["build"]["steps"]
    assert build_steps[-1]["with"]["path"] == "${{ steps.compile.outputs.output }}"
    assert build_steps[-2]["id"] == "compile"
    assert build_steps[-2]["env"]["COMPILER_TOKEN"] == "${{ github.token }}"  # noqa: S105 - Actions expression, not a credential
    assert jobs["build"]["env"]["ESCAPING_VERSION"] == "stable"
    assert jobs["build"]["env"]["SITE_CONFIG"] == "config.yaml"
    assert jobs["build"]["env"]["UV_CACHE_DIR"] == "${{ runner.temp }}/compiler-cache"
    assert yaml.safe_load((_STARTER / "config.yaml").read_text()) == {}
    writing = (_STARTER / ".github/ISSUE_TEMPLATE/write.md").read_text().split("---")[1]
    assert "labels" not in yaml.safe_load(writing)


def test_starter_installs_then_runs_real_console_with_original_config_and_safe_token(
    tmp_path: Path,
    api_transport: tuple[dict, list],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    uv = shutil.which("uv")
    git = shutil.which("git")
    bash = shutil.which("bash")
    assert uv and git and bash
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("UV_", "PYTHON"))
        and k
        not in {
            "VIRTUAL_ENV",
            "GITHUB_TOKEN",
            "GH_TOKEN",
            "PLATFORM_TOKEN",
            "COMPILER_TOKEN",
            "READ_TOKEN",
            "CONSUMER_FAIL_ISSUES",
        }
    }
    site = tmp_path / "site"
    shutil.copytree(_STARTER, site)
    source = tmp_path / "compiler"
    subprocess.run(  # noqa: S603 - local checkout, no remote fetch
        [git, "clone", "--no-hardlinks", str(_ROOT), str(source)],
        env=env,
        check=True,
        capture_output=True,
    )
    sha = subprocess.check_output(  # noqa: S603
        [git, "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    venv = tmp_path / "compiler-env"
    env.update(UV_PROJECT_ENVIRONMENT=str(venv), UV_CACHE_DIR=str(tmp_path / "cache"))
    responses, calls = api_transport
    responses.update(release_responses(sha))
    selected = run_platform("version", monkeypatch, capsys)
    assert selected["commit"] == sha
    assert sum(url.endswith("/releases/latest") for _, url, _ in calls) == 1
    install = [
        bash,
        str(site / ".github/scripts/install.sh"),
        str(source),
        selected["commit"],
        sys.executable,
    ]
    mismatch = subprocess.run(  # noqa: S603
        [*install[:3], "0" * 40, sys.executable],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert mismatch.returncode != 0 and not venv.exists()
    rejected_inputs = []
    for name in ("untracked-source-probe.txt", "ignored-source-probe.log"):
        probe = source / "src/escaping/themes/Quiet/static" / name
        probe.write_text("benign source identity probe\n")
        ignored = subprocess.run(  # noqa: S603 - verify the ignored-input counterexample
            [git, "-C", str(source), "check-ignore", "--quiet", str(probe)],
            env=env,
            capture_output=True,
        )
        assert ignored.returncode == (0 if name.endswith(".log") else 1)
        before_source = {
            p.relative_to(source): p.read_bytes()
            for p in source.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(source).parts
        }
        rejected_venv = tmp_path / (name + "-env")
        untracked = subprocess.run(  # noqa: S603 - real installer and real filesystem
            install,
            env={
                **env,
                "UV_PROJECT_ENVIRONMENT": str(rejected_venv),
                "UV_CACHE_DIR": str(tmp_path / (name + "-cache")),
            },
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        unchanged = before_source == {
            p.relative_to(source): p.read_bytes()
            for p in source.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(source).parts
        }
        rejected_inputs.append(
            {
                "name": name,
                "exit_code": untracked.returncode,
                "venv_created": rejected_venv.exists(),
                "source_unchanged": unchanged,
                "safe_diagnostic": "source contains untracked or ignored files"
                in untracked.stderr,
            }
        )
        (tmp_path / (name + "-install.log")).write_text(
            untracked.stdout + untracked.stderr
        )
        probe.unlink()  # Remove only this test's own sentinel, never git clean.
    (tmp_path / "source-guard.json").write_text(json.dumps(rejected_inputs, indent=2))
    assert all(
        result["exit_code"] != 0
        and not result["venv_created"]
        and result["source_unchanged"]
        and result["safe_diagnostic"]
        for result in rejected_inputs
    ), rejected_inputs
    installed = subprocess.run(  # noqa: S603
        install, env=env, cwd=tmp_path, capture_output=True, text=True
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr
    assert sha in installed.stdout and sys.version.split()[0] in installed.stdout
    assert "lock_sha256" in installed.stdout and "Generator:" in installed.stdout
    source.rename(tmp_path / "source-unavailable")
    python = venv / ("Scripts" if sys.platform == "win32" else "bin") / "python"
    manifest = subprocess.check_output(  # noqa: S603 - installed resources, source hidden
        [
            str(python),
            "-I",
            "-c",
            "from importlib.resources import files; "
            "print(files('escaping').joinpath('themes/Quiet/theme.yaml').read_text())",
        ],
        env=env,
        cwd=tmp_path,
        text=True,
    )
    assert yaml.safe_load(manifest)["api_version"] == "2"
    # Reuse the existing HTTP-only boundary, not its wheel/Theme/config matrix.
    boundary = tmp_path / "http-boundary"
    shutil.copytree(_ROOT / "tests/fixtures/cli_api", boundary)
    config_root = site / "nested site"
    config_root.mkdir()
    config = config_root / "site.yaml"
    config.write_text("security:\n  token_env: READ_TOKEN\npaths:\n  output: public\n")
    context = tmp_path / "context.json"
    prefix = "https://api.github.com/repos/" + _REPOSITORY
    responses[prefix] = {
        "full_name": _REPOSITORY,
        "owner": {"login": "alice", "type": "User"},
    }
    responses[prefix + "/pages"] = {
        "html_url": "https://notes.example/",
        "build_type": "workflow",
    }
    context.write_text(json.dumps(run_platform("context", monkeypatch, capsys)))
    request_log = tmp_path / "requests.log"
    step_output = tmp_path / "step-output"
    step_output.write_text("")
    env.update(
        PYTHONPATH=str(boundary),
        COMPILER_TOKEN="consumer-fixture",  # noqa: S106 - HTTP fixture credential
        CONSUMER_REQUEST_LOG=str(request_log),
        GITHUB_OUTPUT=str(step_output),
        GITHUB_ACTOR="mallory",
    )
    command = [
        str(python),
        str(site / ".github/scripts/run_configured.py"),
        str(config),
        str(context),
    ]
    built = subprocess.run(  # noqa: S603
        command, env=env, cwd=tmp_path, capture_output=True, text=True
    )
    assert built.returncode == 0, built.stdout + built.stderr
    output = config_root / "public"
    assert (output / "blog/128/index.html").is_file()
    assert "Public profile." in (output / "about/index.html").read_text()
    assert step_output.read_text() == f"output={output}\n"
    assert request_log.read_text().splitlines().count("/users/alice") == 1
    before = {
        p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()
    }
    step_output.write_text("")
    failed = subprocess.run(  # noqa: S603
        command,
        env={**env, "CONSUMER_FAIL_ISSUES": "1"},
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert failed.returncode != 0 and "FETCH_FAILED" in failed.stdout
    assert step_output.read_text() == ""
    assert before == {
        p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()
    }
    assert (
        "consumer-fixture"
        not in installed.stdout
        + built.stdout
        + built.stderr
        + failed.stdout
        + failed.stderr
    )
    assert all(b"consumer-fixture" not in value for value in before.values())
    # Transport and filesystem stay real for adapter rejection paths too.
    for overrides, environment in (
        ("security:\n  token_env: PYTHONPATH\n", env),
        ("security:\n  token_env: READ_TOKEN\n", {**env, "READ_TOKEN": "existing"}),
        ("paths:\n  output: ../escape\n", env),
        ("security:\n  token_enf: READ_TOKEN\n", env),
    ):
        config.write_text(overrides)
        request_log.write_text("")
        rejected = subprocess.run(  # noqa: S603
            command, env=environment, cwd=tmp_path, capture_output=True, text=True
        )
        assert rejected.returncode != 0 and not request_log.read_text()
        assert (
            step_output.read_text() == ""
            and "consumer-fixture" not in rejected.stdout + rejected.stderr
        )
    # The shipped {} Config also takes this adapter and the installed CLI path.
    command[-2] = str(site / "config.yaml")
    minimal = subprocess.run(  # noqa: S603
        command,
        env={**env, "GITHUB_TOKEN": "old-value"},
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert minimal.returncode == 0, minimal.stdout + minimal.stderr
    default_output = site / "output"
    assert (default_output / "blog/128/index.html").is_file()
    assert (default_output / "templates/Quiet/static/css/style.css").is_file()
    home = (default_output / "index.html").read_text()
    assert 'href="/templates/Quiet/static/css/style.css"' in home
    # A single default-delivery smoke, not a second Theme/navigation matrix.
    menu = re.search(r'<nav id="site-navigation"[^>]*>(.*?)</nav>', home, re.S)
    assert menu is not None
    links = re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>\s*([^<]+)', menu[1])
    assert [(url, name.strip()) for url, name in links] == [
        ("/", "Home"),
        ("/blog/", "Blog"),
        ("/ideas/", "Ideas"),
        ("/projects/", "Projects"),
        ("/tags/", "Tags"),
        ("/about/", "About"),
        ("/atom.xml", "RSS"),
    ]
    for url, _ in links:
        route = url.lstrip("/") + ("index.html" if url.endswith("/") else "")
        assert (default_output / route).is_file()
    default_files = {
        p.relative_to(default_output): p.read_bytes()
        for p in default_output.rglob("*")
        if p.is_file()
    }
    for path, body in default_files.items():
        assert b"consumer-fixture" not in body
        if path.suffix == ".html":
            assert all(
                marker not in body
                for marker in (
                    b"comments.js",
                    b"data-issue-number",
                    b"utteranc.es",
                    b'id="comments"',
                )
            )
    assert "consumer-fixture" not in minimal.stdout + minimal.stderr
    assert step_output.read_text() == f"output={default_output}\n"
    (tmp_path / "delivery.log").write_text(
        installed.stdout
        + installed.stderr
        + "Installed Quiet manifest:\n"
        + manifest
        + built.stdout
        + failed.stdout
        + minimal.stdout
        + "Verified default delivery: Quiet / Theme API 2 / comments off / seven menu targets exist.\n"
    )
