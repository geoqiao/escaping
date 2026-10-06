"""The escpe command line: exit status, messages and GitHub Actions output.

Builds read Issues from ``--issues-json`` files, as ``gh api --slurp`` writes
them, so no test needs a token or the network.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from escpe.cli import main
from escpe.config import PlatformContext, RepositoryIdentity
from escpe.models.issue_snapshot import IssueSnapshot
from escpe.output_staging import OUTPUT_MARKER
from escpe.services.github_service import PublicProfile

_CONFIG = """\
github:
  repo: alice/site
  allowed_authors: [alice]
site:
  title: Site
  author: Alice
  url: https://example.com/
  description: A site.
profile:
  avatar: ""
  bio: A bio.
security:
  token_env: CLI_TEST_TOKEN
"""
_CONTEXT = {
    "repository": "alice/site",
    "owner_login": "alice",
    "owner_type": "User",
    "pages_base_url": "https://notes.example/",
}


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
        "GITHUB_STEP_SUMMARY",
        "GITHUB_OUTPUT",
    ):
        monkeypatch.delenv(name, raising=False)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    def no_network(token: str) -> None:
        pytest.fail("this build must not contact GitHub")

    monkeypatch.setattr("escpe.cli.GitHubService", no_network)


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


def test_build_is_the_default_and_a_skipped_issue_exits_2(
    site: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = str(site / "config.yaml")
    pages = _issues(tmp_path / "pages.json", [[_GOOD], [_BAD_TAG]])

    assert main(["--config", config, "--issues-json", pages]) == 2

    output = site / "output"
    assert (output / "blog/1/index.html").is_file()
    assert not (output / "blog/3").exists()
    assert (output / OUTPUT_MARKER).is_file()
    assert "A bio." in (output / "about/index.html").read_text(encoding="utf-8")
    err = capsys.readouterr().err
    assert "error: Issue #3: Tag 'C++' must use letters" in err
    assert err.rstrip().endswith(
        "Published output/. Skipped Issues #3; fix the errors above."
    )

    flat = _issues(tmp_path / "flat.json", [_GOOD])
    assert main(["build", "--config", config, "--issues-json", flat]) == 0
    assert not (output / "blog/3").exists()
    assert capsys.readouterr().err.rstrip().endswith("Published output/.")


def test_failed_build_leaves_the_previous_output(
    site: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = site / "config.yaml"
    issues = _issues(tmp_path / "issues.json", [_GOOD])
    assert main(["--config", str(config), "--issues-json", issues]) == 0
    before = _files(site / "output")

    config.write_text(_CONFIG + "about:\n  issue_number: 9\n", encoding="utf-8")
    capsys.readouterr()
    assert main(["--config", str(config), "--issues-json", issues]) == 1

    assert _files(site / "output") == before
    err = capsys.readouterr().err
    assert "error: about.issue_number #9 was not found\n" in err
    assert err.rstrip().endswith(
        "Build failed; the previous output was left unchanged."
    )


def test_a_build_without_a_token_or_issues_file_names_the_variable(
    site: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(site)  # no arguments: build ./config.yaml

    assert main([]) == 1
    assert capsys.readouterr().err == (
        "error: set the CLI_TEST_TOKEN environment variable to a GitHub token, "
        "or pass --issues-json\nNothing was built.\n"
    )
    monkeypatch.setenv("CLI_TEST_TOKEN", "unused")
    assert main(["--token-env", "READ_TOKEN"]) == 1
    assert "set the READ_TOKEN environment variable" in capsys.readouterr().err
    assert not (site / "output").exists()


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
    config = str(site / "config.yaml")
    output = (site / "output").resolve()

    issues = _issues(tmp_path / "issues.json", [_GOOD, _BAD_TAG, _OTHER_AUTHOR])
    assert main(["--config", config, "--issues-json", issues]) == 2
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
    assert text.startswith("## escaping\n\nPublished output/. Skipped Issues #3;")
    assert "| ❌ | [#3](https://github.com/alice/site/issues/3) | Issue #3: Tag" in text
    assert "| ⚠️ | [#4](https://github.com/alice/site/issues/4) |" in text
    assert outputs.read_text(encoding="utf-8") == (
        f"output={output}\nskipped-issues=3\n"
    )

    clean = _issues(tmp_path / "clean.json", [_GOOD])
    assert main(["--config", config, "--issues-json", clean]) == 0
    assert outputs.read_text(encoding="utf-8").endswith(
        f"output={output}\nskipped-issues=\n"
    )

    # A failed build is not uploaded, so it sets no outputs.
    written = outputs.read_text(encoding="utf-8")
    (site / "config.yaml").write_text(_CONFIG + "seo: {social_image: x}\n", "utf-8")
    assert main(["--config", config, "--issues-json", clean]) == 1
    assert outputs.read_text(encoding="utf-8") == written
    assert "::error title=CONFIG_INVALID::seo.social_image:" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("config", "files", "expected"),
    [
        ("{}\n", {}, "Theme quiet renders every page."),
        (
            "theme:\n  options: {taglin: x}\n",
            {},
            "theme.options.taglin: quiet has no such option; did you mean tagline?",
        ),
        (
            "theme: {use: ./my-theme}\n",
            {"home.html": "{% if %}"},
            "my-theme: home.html line 1:",
        ),
        (
            "theme: {use: ./my-theme}\n",
            {"home.html": "{{ no_such_value.title }}"},
            "'no_such_value' is undefined",
        ),
        (
            "theme: {use: ./my-theme}\n",
            {"theme.yaml": "api: 3\n"},
            "my-theme: theme.yaml must declare api: 4",
        ),
    ],
)
def test_theme_check_renders_sample_content_offline(
    config: str,
    files: dict[str, str],
    expected: str,
    site: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (site / "config.yaml").write_text(config, encoding="utf-8")
    if files:
        theme = site / "my-theme"
        theme.mkdir()
        (theme / "theme.yaml").write_text("api: 4\nextends: quiet\n")
        for name, text in files.items():
            (theme / name).write_text(text, encoding="utf-8")

    status = main(["theme", "check", "--config", str(site / "config.yaml")])

    err = capsys.readouterr().err
    assert expected in err, err
    assert status == (0 if config == "{}\n" else 1)
    if status:
        assert err.rstrip().endswith("Theme check failed.")
    assert not (site / "output").exists()


def test_theme_check_can_render_saved_issues(
    site: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    issues = _issues(tmp_path / "issues.json", [[_GOOD]])
    config = str(site / "config.yaml")
    assert main(["theme", "check", "--config", config, "--issues-json", issues]) == 0
    assert "Theme quiet renders every page." in capsys.readouterr().err


@pytest.mark.parametrize(
    ("data", "problem"),
    [
        ('{"message": "Bad credentials"}', "issues.json: expected a JSON list"),
        ('[[{"title": "no number"}]]', "issues.json: item 0 is not a GitHub Issue"),
        ("not json", "not valid JSON"),
    ],
)
def test_a_bad_issues_file_builds_nothing(
    data: str,
    problem: str,
    site: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    issues = tmp_path / "issues.json"
    issues.write_text(data, encoding="utf-8")
    config = str(site / "config.yaml")

    assert main(["--config", config, "--issues-json", str(issues)]) == 1
    err = capsys.readouterr().err
    assert problem in err and err.endswith("Nothing was built.\n")
    assert not (site / "output").exists()


@pytest.mark.parametrize(
    ("config", "context"),
    [
        (_CONFIG.replace("https://example.com/", "https://u:ghp_SECRET@x.test/"), None),
        (_CONFIG.replace("url: https://example.com/", "url: [ghp_SECRET"), None),
        (_CONFIG + "security: {token_env: ghp_SECRET-1}\n", None),
        (
            "security: {token_env: CLI_TEST_TOKEN}\n",
            {**_CONTEXT, "pages_base_url": "https://ghp_SECRET.example/a b/"},
        ),
        (
            "security: {token_env: CLI_TEST_TOKEN}\n",
            {**_CONTEXT, "owner_login": "ghp_SECRET"},
        ),
    ],
)
def test_input_errors_never_echo_supplied_values(
    config: str,
    context: dict[str, str] | None,
    site: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (site / "config.yaml").write_text(config, encoding="utf-8")
    args = ["--config", str(site / "config.yaml")]
    args += ["--issues-json", _issues(tmp_path / "issues.json", [_GOOD])]
    if context is not None:
        args += ["--context", _issues(tmp_path / "context.json", context)]

    assert main(args) == 1
    captured = capsys.readouterr()
    assert "ghp_SECRET" not in captured.out + captured.err
    assert captured.err.endswith("Nothing was built.\n")


def test_online_build_reads_github_and_keeps_the_token_private(
    site: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
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

        def fetch_public_profile(self, login: str) -> PublicProfile:
            raise RuntimeError(f"profile failed for {secret}")

        def fetch_project_enrichment(self, repository: str) -> object:
            raise RuntimeError(f"token={secret}")

    monkeypatch.setattr("escpe.cli.GitHubService", FakeGitHub)
    monkeypatch.setenv("READ_TOKEN", secret)
    config = site / "config.yaml"
    config.write_text("projects:\n  - repository: alice/tool\n", encoding="utf-8")
    context = _issues(tmp_path / "context.json", _CONTEXT)
    args = ["--config", str(config), "--context", context, "--token-env", "READ_TOKEN"]

    assert main(args) == 0
    assert tokens == [secret]
    output = site / "output"
    assert (output / "blog/1/index.html").is_file()
    assert "https://notes.example/blog/1/" in (output / "sitemap.xml").read_text()
    before = _files(output)
    first = capsys.readouterr()
    assert "warning: Public Profile unavailable" in first.err
    assert "warning: Project alice/tool metadata enrichment failed" in first.err

    FakeGitHub.fail = True
    assert main(args) == 1
    assert _files(output) == before
    second = capsys.readouterr()
    assert "error: could not read the Issues of the content repository" in second.err
    for text in (first.out, first.err, second.out, second.err):
        assert secret not in text
    assert all(secret.encode() not in content for content in before.values())


def test_on_github_actions_the_command_reads_what_the_config_leaves_out(
    site: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    asked: list[str] = []

    class FakeGitHub:
        def __init__(self, token: str) -> None:
            pass

        def get_repo(self, name: str) -> str:
            return name

        def fetch_issue_snapshots(self, repo: str) -> list[IssueSnapshot]:
            labels = ("published", "type:blog")
            return [IssueSnapshot(1, "Post", "alice", "Body.", labels, now, now, False)]

        def fetch_platform_context(self, repository: str) -> PlatformContext:
            asked.append(repository)
            return PlatformContext.model_validate(_CONTEXT)

        def fetch_project_enrichment(self, repository: str) -> object:
            raise AssertionError("this site lists no projects")

        def fetch_public_profile(self, login: str) -> PublicProfile:
            return PublicProfile(login, "Alice")

    monkeypatch.setattr("escpe.cli.GitHubService", FakeGitHub)
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPOSITORY", "alice/site")
    empty = site / "config.yaml"
    empty.write_text("{}\n", encoding="utf-8")

    # A laptop with a token is not GitHub Actions: nothing is guessed.
    assert main(["--config", str(empty)]) == 1
    assert not asked

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert main(["--config", str(empty)]) == 0
    assert asked == ["alice/site"]
    assert "https://notes.example/blog/1/" in (site / "output/sitemap.xml").read_text()

    # A Config that names its repository and address is never asked about Pages.
    full = tmp_path / "full"
    full.mkdir()
    (full / "config.yaml").write_text(_CONFIG, encoding="utf-8")
    monkeypatch.setenv("CLI_TEST_TOKEN", "t")
    assert main(["--config", str(full / "config.yaml")]) == 0
    assert asked == ["alice/site"]
