"""The GitHub adapter: Issues become snapshots of plain values.

It reads ``state=all`` Issues with GET requests only (the local server below
answers nothing else), and tells a pull request apart from the list response
without one extra request per Issue.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
from github import Github
from github.Issue import Issue as PyGithubIssue

from escaping.config import Settings
from escaping.models.issue_snapshot import IssueSnapshot
from escaping.output_staging import OUTPUT_MARKER
from escaping.services.github_service import (
    GitHubService,
    _to_issue_snapshot,
    read_issues_json,
)
from escaping.site_compiler import SiteCompiler


@pytest.mark.parametrize(
    ("scenario", "status"),
    [("recover", 503), ("recover", 403), ("forbidden", 403), ("exhausted", 503)],
)
def test_request_retries_recover_pagination_or_preserve_previous_output(
    scenario: str, status: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests: Counter[str] = Counter()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            url = urlsplit(self.path)
            key = url.path + ("?page=2" if "page=2" in url.query else "")
            requests[key] += 1
            assert self.headers["Authorization"] == "token test-token"
            headers = {}
            code = 200
            if url.path == "/repos/owner/site":
                payload = {"url": origin + "/repos/owner/site"}
                if scenario == "forbidden":
                    code, payload = 403, {"message": "Resource not accessible"}
            else:
                assert url.path == "/repos/owner/site/issues"
                assert parse_qs(url.query)["state"] == ["all"]
                page = 2 if "page=2" in url.query else 1
                if page == 1:
                    headers["Link"] = (
                        f'<{origin}{url.path}?state=all&page=2>; rel="next"'
                    )
                payload = [
                    {
                        "number": page,
                        "title": f"Post {page}",
                        "body": "A post.",
                        "user": {"login": "owner"},
                        "labels": [{"name": "type:blog"}, {"name": "published"}],
                        "created_at": "2026-01-01T00:00:00Z",
                        "updated_at": "2026-01-02T00:00:00Z",
                    }
                ]
                if page == 2 and (scenario == "exhausted" or requests[key] == 1):
                    code, payload = status, {"message": "API rate limit exceeded"}
                    if status == 403:
                        headers["Retry-After"] = "0"
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for name, value in headers.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    origin = f"http://127.0.0.1:{server.server_port}"
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # Keep PyGithub's real HTTP adapter and default retry policy; use local HTTP only.
    monkeypatch.setattr(
        "escaping.services.github_service.Github",
        partial(Github, base_url=origin, seconds_between_requests=0),
    )
    service = GitHubService("test-token")
    settings = Settings.model_validate(
        {
            "github": {"repo": "owner/site", "allowed_authors": ["owner"]},
            "site": {"title": "Site", "author": "Owner", "url": "https://example.org/"},
        }
    )
    output = tmp_path / "output"
    output.mkdir()
    (output / OUTPUT_MARKER).write_text("previous build", encoding="utf-8")
    sentinel = output / "index.html"
    sentinel.write_bytes(b"Previous site")
    try:
        result = SiteCompiler(
            settings,
            config_root=tmp_path,
            issues=lambda: service.fetch_issue_snapshots(
                service.get_repo("owner/site")
            ),
        ).generate()
        assert requests["/repos/owner/site"] == 1
        if scenario == "recover":
            assert result.success, result.diagnostics
            assert requests["/repos/owner/site/issues"] == 1
            assert requests["/repos/owner/site/issues?page=2"] == 2
            for number in (1, 2):
                assert (output / f"blog/{number}/index.html").is_file()
        else:
            assert not result.success
            assert [d.code for d in result.diagnostics] == ["FETCH_FAILED"]
            assert sorted(output.iterdir()) == [output / OUTPUT_MARKER, sentinel]
            assert sentinel.read_bytes() == b"Previous site"
            assert not list(tmp_path.glob(".output.staging.*"))
            if scenario == "exhausted":
                assert requests["/repos/owner/site/issues"] == 1
                retry_limit = Github.default_retry.total
                assert isinstance(retry_limit, int)
                assert requests["/repos/owner/site/issues?page=2"] == retry_limit + 1
    finally:
        service.gh.close()
        server.shutdown()
        thread.join()
        server.server_close()


# ---------------------------------------------------------------------------
# Snapshots hold plain values, read from the list response only
# ---------------------------------------------------------------------------


def test_snapshots_copy_the_issue_without_a_detail_request() -> None:
    """Snapshot conversion must not trigger per-Issue detail GET (N+1).

    PyGithub's ``Issue.pull_request`` property calls ``_completeIfNotSet``
    which issues a GET when the ``pull_request`` key is absent from the
    list-response payload.  Reading ``_rawData`` directly avoids this.
    """
    requester = MagicMock()
    requester.is_not_lazy = False

    base_raw = {
        "title": "Using Rust",
        "body": "body",
        "user": {"login": "alice"},
        "labels": [{"name": "type:blog"}],
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
    }

    # Case 1: pull_request key absent (worst case for N+1)
    raw_missing = dict(
        base_raw, number=42, url="https://api.github.com/repos/o/r/issues/42"
    )
    snap_missing = _to_issue_snapshot(PyGithubIssue(requester, {}, raw_missing))
    requester.requestJsonAndCheck.assert_not_called()
    assert snap_missing == IssueSnapshot(
        number=42,
        title="Using Rust",
        author="alice",
        body="body",
        labels=("type:blog",),
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 2, tzinfo=UTC),
        is_pull_request=False,
    )

    # Case 2: pull_request present as dict (real PR)
    raw_pr = dict(base_raw, number=7, url="https://api.github.com/repos/o/r/issues/7")
    raw_pr["pull_request"] = {
        "url": "https://api.github.com/repos/o/r/pulls/7",
        "html_url": "https://github.com/o/r/pull/7",
        "diff_url": "https://github.com/o/r/pull/7.diff",
        "patch_url": "https://github.com/o/r/pull/7.patch",
    }
    snap_pr = _to_issue_snapshot(PyGithubIssue(requester, {}, raw_pr))
    requester.requestJsonAndCheck.assert_not_called()
    assert snap_pr.is_pull_request is True
    assert snap_pr.number == 7


@patch("escaping.services.github_service.Github")
def test_public_profile_and_repository_identity_are_plain_verified_snapshots(
    mock_github_class: MagicMock,
) -> None:
    from github.NamedUser import NamedUser
    from github.Repository import Repository
    from pydantic import ValidationError

    requester = MagicMock()
    requester.is_not_lazy = False
    user = NamedUser(
        requester,
        {},
        {
            "login": "alice",
            "name": "Alice Example",
            "bio": "Hello",
            "avatar_url": "https://example.org/a.png",
        },
        completed=True,
    )
    mock_github_class.return_value.get_user.return_value = user
    service = GitHubService("fake-token")
    profile = service.fetch_public_profile("alice")
    assert (profile.login, profile.name, profile.avatar_url, profile.bio) == (
        "alice",
        "Alice Example",
        "https://example.org/a.png",
        "Hello",
    )
    requester.requestJsonAndCheck.assert_not_called()
    base = {
        "full_name": "Alice/Site",
        "html_url": "https://github.com/Alice/Site",
        "owner": {"login": "Alice", "type": "User"},
    }
    mock_github_class.return_value.get_repo.return_value = Repository(
        requester, {}, base, completed=True
    )
    identity = service.fetch_repository_identity("alice/site")
    assert identity.owner_login == "Alice" and identity.owner_type == "User"
    for patch_data in (
        {"full_name": "alice/renamed"},
        {"html_url": "https://enterprise.example/alice/site"},
        {"owner": {"login": "mallory", "type": "User"}},
        {"owner": {"login": "alice", "type": "Bot"}},
    ):
        mock_github_class.return_value.get_repo.return_value = Repository(
            requester, {}, {**base, **patch_data}, completed=True
        )
        with pytest.raises((ValueError, ValidationError)):
            service.fetch_repository_identity("alice/site")


# ---------------------------------------------------------------------------
# --issues-json: Issues saved with gh api, read offline
# ---------------------------------------------------------------------------


def _raw_issue(number: int, **extra: object) -> dict[str, object]:
    return {
        "number": number,
        "title": f"Post {number}",
        "body": None,
        "user": {"login": "alice"},
        "labels": [{"name": "type:blog"}, {"name": "published"}],
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00+00:00",
        **extra,
    }


def test_read_issues_json_accepts_gh_slurp_pages_and_a_flat_list(
    tmp_path: Path,
) -> None:
    path = tmp_path / "issues.json"
    pr = _raw_issue(3, pull_request={"url": "https://api.github.com/x"})
    path.write_text(
        json.dumps([[_raw_issue(1), _raw_issue(2, pull_request=None)], [pr]]),
        encoding="utf-8",
    )
    pages = read_issues_json(path)
    assert [(s.number, s.is_pull_request) for s in pages] == [
        (1, False),
        (2, False),
        (3, True),
    ]
    first = pages[0]
    assert (first.author, first.body, first.labels) == (
        "alice",
        "",
        ("type:blog", "published"),
    )
    assert first.created_at == datetime(2026, 1, 1, tzinfo=UTC)

    path.write_text(json.dumps([_raw_issue(1), _raw_issue(2), pr]), encoding="utf-8")
    assert read_issues_json(path) == pages
    path.write_text("[]", encoding="utf-8")
    assert read_issues_json(path) == []


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"message": "Bad credentials"}, "issues.json: expected a JSON list of Issues"),
        ([[_raw_issue(1)], ["secret-text"]], "issues.json: item 1 is not a GitHub"),
        ([{"title": "no number"}], "issues.json: item 0 is not a GitHub Issue"),
        ([_raw_issue(1, created_at="yesterday")], "item 0 is not a GitHub Issue"),
        (
            [_raw_issue(1, updated_at="2026-01-02T00:00:00")],
            "item 0 is not a GitHub Issue",
        ),
        ([_raw_issue(1, labels=["type:blog"])], "item 0 is not a GitHub Issue"),
    ],
)
def test_read_issues_json_names_the_bad_item_without_echoing_it(
    data: object, message: str, tmp_path: Path
) -> None:
    path = tmp_path / "issues.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match=message) as error:
        read_issues_json(path)
    assert "secret" not in str(error.value) and "yesterday" not in str(error.value)
