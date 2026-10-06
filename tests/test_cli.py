"""The escaping-site command line: exit status, messages and GitHub Actions output.

Exports read Issues from ``--issues-json`` files, as ``gh api --slurp`` writes
them, so no test needs a token or the network. The exported files belong to
``test_content_export.py``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from escaping_site.cli import main
from escaping_site.config import RepositoryIdentity
from escaping_site.models.issue_snapshot import IssueSnapshot

_CONFIG = """\
github:
  repo: alice/site
  allowed_authors: [alice]
security:
  token_env: CLI_TEST_TOKEN
"""


def _issue(number: int, *labels: str, author: str = "alice") -> dict[str, object]:
    return {
        "number": number,
        "title": f"Issue {number}",
        "body": "Body.",
        "user": {"login": author},
        "labels": [{"name": name} for name in ("published", *labels)],
        "created_at": f"2026-01-0{number}T00:00:00Z",
        "updated_at": f"2026-01-0{number}T00:00:00Z",
        "pull_request": None,
    }


_GOOD = _issue(1, "type:blog", "tag:Notes")
_BAD_TAG = _issue(3, "type:blog", "tag:C++")
_OTHER_AUTHOR = _issue(4, "type:blog", author="mallory")


@pytest.fixture(autouse=True)
def _clean_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "CLI_TEST_TOKEN",
        "GITHUB_TOKEN",
        "READ_TOKEN",
        "GITHUB_ACTIONS",
        "GITHUB_REPOSITORY",
        "GITHUB_STEP_SUMMARY",
        "GITHUB_OUTPUT",
    ):
        monkeypatch.delenv(name, raising=False)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    def no_network(token: str) -> None:
        pytest.fail("this export must not contact GitHub")

    monkeypatch.setattr("escaping_site.cli.GitHubService", no_network)


@pytest.fixture
def site(tmp_path: Path) -> Path:
    directory = tmp_path / "site"
    directory.mkdir()
    (directory / "config.yaml").write_text(_CONFIG, encoding="utf-8")
    return directory


def _issues(path: Path, data: object) -> str:
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def _files(directory: Path) -> dict[Path, bytes]:
    return {
        p.relative_to(directory): p.read_bytes()
        for p in directory.rglob("*")
        if p.is_file()
    }


def test_a_command_is_required_and_the_removed_build_is_refused(
    capsys: pytest.CaptureFixture[str],
) -> None:
    for args in ([], ["build"], ["theme", "check"]):
        with pytest.raises(SystemExit) as exit_info:
            main(args)
        assert exit_info.value.code == 2
    assert "export" in capsys.readouterr().err


def test_a_failed_export_leaves_the_previous_one(
    site: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = site / "config.yaml"
    issues = _issues(tmp_path / "issues.json", [[_GOOD], [_BAD_TAG]])
    assert main(["export", "--config", str(config), "--issues-json", issues]) == 2
    before = _files(site / "build/content")
    assert Path("blog/1.md") in before and Path("blog/3.md") not in before

    config.write_text(_CONFIG + "about:\n  issue_number: 9\n", encoding="utf-8")
    capsys.readouterr()
    assert main(["export", "--config", str(config), "--issues-json", issues]) == 1

    assert _files(site / "build/content") == before
    err = capsys.readouterr().err
    assert "error: about.issue_number #9 was not found\n" in err
    assert err.rstrip().endswith(
        "Export failed; the previous export was left unchanged."
    )


def test_an_export_without_a_token_or_issues_file_names_the_variable(
    site: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(site)  # no --config: ./config.yaml

    assert main(["export"]) == 1
    assert capsys.readouterr().err == (
        "error: set the CLI_TEST_TOKEN environment variable to a GitHub token, "
        "or pass --issues-json\nNothing was exported.\n"
    )
    monkeypatch.setenv("CLI_TEST_TOKEN", "unused")
    assert main(["export", "--token-env", "READ_TOKEN"]) == 1
    assert "set the READ_TOKEN environment variable" in capsys.readouterr().err
    assert not (site / "build").exists()


def test_github_actions_get_annotations_a_job_summary_and_step_outputs(
    site: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    summary = tmp_path / "summary.md"
    outputs = tmp_path / "outputs.txt"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("GITHUB_OUTPUT", str(outputs))
    args = ["export", "--config", str(site / "config.yaml"), "--issues-json"]
    output = (site / "build/content").resolve()

    issues = _issues(tmp_path / "issues.json", [_GOOD, _BAD_TAG, _OTHER_AUTHOR])
    assert main([*args, issues]) == 2
    stdout = capsys.readouterr().out.splitlines()
    assert any(
        line.startswith("::error title=TAG_INVALID::Issue #3: Tag 'C++'")
        for line in stdout
    ), stdout
    assert (
        "::warning title=UNAUTHORIZED_AUTHOR::"
        "Issue #4: author is not in allowed_authors"
    ) in stdout
    text = summary.read_text(encoding="utf-8")
    assert text.startswith("## escaping\n\nExported build/content/. Skipped Issues #3;")
    assert "| ❌ | [#3](https://github.com/alice/site/issues/3) | Issue #3: Tag" in text
    assert "| ⚠️ | [#4](https://github.com/alice/site/issues/4) |" in text
    assert outputs.read_text(encoding="utf-8") == (
        f"output={output}\nskipped-issues=3\n"
    )

    clean = _issues(tmp_path / "clean.json", [_GOOD])
    assert main([*args, clean]) == 0
    assert outputs.read_text(encoding="utf-8").endswith(
        f"output={output}\nskipped-issues=\n"
    )

    # A failed export sets no outputs.
    written = outputs.read_text(encoding="utf-8")
    (site / "config.yaml").write_text(_CONFIG + "about: {issue: 1}\n", "utf-8")
    assert main([*args, clean]) == 1
    assert outputs.read_text(encoding="utf-8") == written
    assert "::error title=CONFIG_INVALID::about.issue:" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("data", "problem"),
    [
        ('{"message": "Bad credentials"}', "issues.json: expected a JSON list"),
        ('[[{"title": "no number"}]]', "issues.json: item 0 is not a GitHub Issue"),
        ("not json", "not valid JSON"),
    ],
)
def test_a_bad_issues_file_exports_nothing(
    data: str,
    problem: str,
    site: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    issues = tmp_path / "issues.json"
    issues.write_text(data, encoding="utf-8")
    config = str(site / "config.yaml")

    assert main(["export", "--config", config, "--issues-json", str(issues)]) == 1
    err = capsys.readouterr().err
    assert problem in err and err.endswith("Nothing was exported.\n")
    assert not (site / "build").exists()


@pytest.mark.parametrize(
    "config",
    [
        _CONFIG.replace("alice/site", "ghp_SECRET"),
        _CONFIG.replace("repo: alice/site", "repo: [ghp_SECRET"),
        _CONFIG.replace("CLI_TEST_TOKEN", "ghp_SECRET-1"),
        _CONFIG.replace("[alice]", "[ghp_SECRET, ghp_SECRET]"),
    ],
)
def test_input_errors_never_echo_supplied_values(
    config: str, site: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (site / "config.yaml").write_text(config, encoding="utf-8")
    issues = _issues(tmp_path / "issues.json", [_GOOD])

    args = ["export", "--config", str(site / "config.yaml"), "--issues-json", issues]
    assert main(args) == 1
    captured = capsys.readouterr()
    assert "ghp_SECRET" not in captured.out + captured.err
    assert captured.err.endswith("Nothing was exported.\n")


def test_an_online_export_reads_github_and_keeps_the_token_private(
    site: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret = "super-secret-token"  # noqa: S105 - controlled test credential
    now = datetime(2026, 1, 1, tzinfo=UTC)
    tokens: list[str] = []

    class FakeGitHub:
        fail = False

        def __init__(self, token: str) -> None:
            tokens.append(token)

        def get_repo(self, name: str) -> str:
            return name

        def fetch_issue_snapshots(self, repo: str) -> list[IssueSnapshot]:
            if self.fail:
                raise RuntimeError(f"401 for token {secret}")
            assert repo == "alice/site"
            labels = ("published", "type:blog")
            return [IssueSnapshot(1, "Post", "alice", "Body.", labels, now, now, False)]

        def fetch_repository_identity(self, repository: str) -> RepositoryIdentity:
            return RepositoryIdentity(
                repository=repository, owner_login="alice", owner_type="User"
            )

    monkeypatch.setattr("escaping_site.cli.GitHubService", FakeGitHub)
    monkeypatch.setenv("READ_TOKEN", secret)
    config = site / "config.yaml"
    # The owner of a personal repository is the author when none is named.
    config.write_text("github: {repo: alice/site}\n", encoding="utf-8")
    args = ["export", "--config", str(config), "--token-env", "READ_TOKEN"]

    assert main(args) == 0
    assert tokens == [secret]
    before = _files(site / "build/content")
    assert Path("blog/1.md") in before
    first = capsys.readouterr()

    FakeGitHub.fail = True
    assert main(args) == 1
    assert _files(site / "build/content") == before
    second = capsys.readouterr()
    assert "error: could not read the Issues of the content repository" in second.err
    for text in (first.out, first.err, second.out, second.err):
        assert secret not in text
    assert all(secret.encode() not in content for content in before.values())
