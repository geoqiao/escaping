"""Behavioral tests for the issue-ingestion seam (Ticket 01).

The GitHub adapter fetches ``state=all`` Issues and produces immutable
``IssueSnapshot`` values without leaking PyGithub objects past the boundary
and without mutating any Issue or repository.

Critical regression: PR identity is read from ``_rawData`` (list-response
payload) without triggering per-Issue lazy completion (N+1).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from github.Issue import Issue as PyGithubIssue

from escaping.services.github_service import GitHubService, _to_issue_snapshot


def _make_label(name: str) -> MagicMock:
    m = MagicMock()
    m.name = name
    return m


def _make_user(login: str) -> MagicMock:
    m = MagicMock()
    m.login = login
    return m


def _make_issue(
    number: int,
    *,
    title: str = "Title",
    body: str = "body",
    author: str = "alice",
    labels: list[str] | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    is_pr: bool = False,
) -> MagicMock:
    issue = MagicMock()
    issue.number = number
    issue.title = title
    issue.body = body
    issue.user = _make_user(author)
    issue.labels = [_make_label(name) for name in (labels or [])]
    issue.created_at = created_at or datetime(2024, 1, 1, tzinfo=UTC)
    issue.updated_at = updated_at or datetime(2024, 1, 2, tzinfo=UTC)
    issue._rawData = (
        {"pull_request": {"url": "https://api.github.com/repos/o/r/pulls/1"}}
        if is_pr
        else {"pull_request": None}
    )
    return issue


def _make_repo(issues: list[MagicMock]) -> MagicMock:
    repo = MagicMock()
    repo.get_issues.return_value = issues
    return repo


# ---------------------------------------------------------------------------
# fetch_issue_snapshots: conversion, selection, determinism
# ---------------------------------------------------------------------------


@patch("escaping.services.github_service.Github")
def test_fetch_issue_snapshots_converts_and_selects(
    mock_github_class: MagicMock,
) -> None:
    service = GitHubService("fake-token")
    created = datetime(2024, 3, 1, 12, 0, tzinfo=UTC)
    updated = datetime(2024, 3, 2, 8, 30, tzinfo=UTC)
    plain = _make_issue(
        42,
        title="Using Rust",
        body="---\nslug: x\n---\nbody",
        author="alice",
        labels=["type:blog", "published", "tag:rust"],
        created_at=created,
        updated_at=updated,
    )
    pr = _make_issue(2, is_pr=True)
    repo = _make_repo([plain, pr])

    snapshots = service.fetch_issue_snapshots(repo)

    # Queries state=all
    repo.get_issues.assert_called_once_with(state="all")
    assert len(snapshots) == 2
    snap = snapshots[0]
    assert snap.number == 42
    assert snap.title == "Using Rust"
    assert snap.author == "alice"
    assert snap.body == "---\nslug: x\n---\nbody"
    assert snap.labels == ("type:blog", "published", "tag:rust")
    assert snap.created_at == created
    assert snap.updated_at == updated
    # PR identity recorded
    assert snapshots[0].is_pull_request is False
    assert snapshots[1].is_pull_request is True
    # Deterministic: same inputs produce same snapshots
    repo_b = _make_repo(
        [
            _make_issue(
                42,
                title="Using Rust",
                body="---\nslug: x\n---\nbody",
                author="alice",
                labels=["type:blog", "published", "tag:rust"],
                created_at=created,
                updated_at=updated,
            )
        ]
    )
    assert (
        service.fetch_issue_snapshots(repo)[0]
        == service.fetch_issue_snapshots(repo_b)[0]
    )
    # Empty repo returns empty list
    assert service.fetch_issue_snapshots(_make_repo([])) == []


# ---------------------------------------------------------------------------
# No PyGithub objects leak; no mutation
# ---------------------------------------------------------------------------


@patch("escaping.services.github_service.Github")
def test_no_leak_and_no_mutation(mock_github_class: MagicMock) -> None:
    service = GitHubService("fake-token")
    issue = _make_issue(1, author="alice", labels=["type:blog"], is_pr=True)
    repo = _make_repo([issue])

    snap = service.fetch_issue_snapshots(repo)[0]

    # Only plain Python fields escape the boundary
    for field_name in (
        "number",
        "title",
        "author",
        "body",
        "labels",
        "created_at",
        "updated_at",
        "is_pull_request",
    ):
        value = getattr(snap, field_name)
        assert not isinstance(value, MagicMock), (
            f"field {field_name!r} leaked a PyGithub object"
        )
    assert all(isinstance(label, str) for label in snap.labels)
    # Adapter is read-only
    issue.edit.assert_not_called()
    issue.add_to_labels.assert_not_called()
    issue.set_labels.assert_not_called()
    issue.create_comment.assert_not_called()
    repo.create_issue.assert_not_called()
    repo.edit.assert_not_called()


# ---------------------------------------------------------------------------
# PR identity without N+1 (reads _rawData, not Issue.pull_request property)
# ---------------------------------------------------------------------------


def test_pr_identity_without_detail_request() -> None:
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
    assert snap_missing.is_pull_request is False
    assert snap_missing.number == 42

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
