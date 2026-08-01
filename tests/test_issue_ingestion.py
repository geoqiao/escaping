"""Behavioral tests for the Ticket 01 issue-ingestion seam.

The pre-agreed test seam is the GitHub adapter external interface: it fetches
``state=all`` Issues and produces immutable, in-memory ``IssueSnapshot`` values
without leaking PyGithub objects past the boundary and without mutating any
Issue or repository.
"""

from __future__ import annotations

import dataclasses
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from github.Issue import Issue as PyGithubIssue

from github_blog.models.issue_snapshot import IssueSnapshot
from github_blog.services.github_service import GitHubService, _to_issue_snapshot


def _make_label(name: str) -> MagicMock:
    label = MagicMock()
    label.name = name
    return label


def _make_user(login: str) -> MagicMock:
    user = MagicMock()
    user.login = login
    return user


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
    issue.created_at = created_at or datetime(2024, 1, 1, tzinfo=timezone.utc)
    issue.updated_at = updated_at or datetime(2024, 1, 2, tzinfo=timezone.utc)
    # PR identity is read from the raw list-response payload (_rawData), not
    # from the pull_request property, to avoid per-Issue lazy completion.
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


@patch("github_blog.services.github_service.Github")
def test_fetch_issue_snapshots_queries_state_all(
    mock_github_class: MagicMock,
) -> None:
    service = GitHubService("fake-token")
    repo = _make_repo([])

    service.fetch_issue_snapshots(repo)

    repo.get_issues.assert_called_once_with(state="all")


@patch("github_blog.services.github_service.Github")
def test_fetch_issue_snapshots_empty_returns_empty_list(
    mock_github_class: MagicMock,
) -> None:
    service = GitHubService("fake-token")
    repo = _make_repo([])

    snapshots = service.fetch_issue_snapshots(repo)

    assert snapshots == []


@patch("github_blog.services.github_service.Github")
def test_fetch_issue_snapshots_converts_required_fields(
    mock_github_class: MagicMock,
) -> None:
    service = GitHubService("fake-token")
    issue = _make_issue(
        42,
        title="Using Rust",
        # The raw body (front matter included) passes through unchanged; front
        # matter parsing is a downstream concern, not the adapter's job.
        body="---\nslug: x\n---\nbody",
        author="alice",
        labels=["type:blog", "published", "tag:rust"],
        created_at=datetime(2024, 3, 1, 12, 0, tzinfo=timezone.utc),
        updated_at=datetime(2024, 3, 2, 8, 30, tzinfo=timezone.utc),
    )
    repo = _make_repo([issue])

    snapshots = service.fetch_issue_snapshots(repo)

    assert len(snapshots) == 1
    snap = snapshots[0]
    assert snap.number == 42
    assert snap.title == "Using Rust"
    assert snap.author == "alice"
    assert snap.body == "---\nslug: x\n---\nbody"
    assert snap.created_at == datetime(2024, 3, 1, 12, 0, tzinfo=timezone.utc)
    assert snap.updated_at == datetime(2024, 3, 2, 8, 30, tzinfo=timezone.utc)


@patch("github_blog.services.github_service.Github")
def test_fetch_issue_snapshots_records_pull_request_identity(
    mock_github_class: MagicMock,
) -> None:
    service = GitHubService("fake-token")
    plain = _make_issue(1, is_pr=False)
    pr = _make_issue(2, is_pr=True)
    repo = _make_repo([plain, pr])

    snapshots = service.fetch_issue_snapshots(repo)

    assert snapshots[0].is_pull_request is False
    assert snapshots[1].is_pull_request is True


@patch("github_blog.services.github_service.Github")
def test_fetch_issue_snapshots_author_and_label_values(
    mock_github_class: MagicMock,
) -> None:
    service = GitHubService("fake-token")
    issue = _make_issue(
        7,
        author="Bob",
        labels=["type:idea", "tag:daily-life", "tag:python"],
    )
    repo = _make_repo([issue])

    snap = service.fetch_issue_snapshots(repo)[0]

    assert snap.author == "Bob"
    assert snap.labels == ("type:idea", "tag:daily-life", "tag:python")


@patch("github_blog.services.github_service.Github")
def test_fetch_issue_snapshots_labels_are_immutable_tuple(
    mock_github_class: MagicMock,
) -> None:
    service = GitHubService("fake-token")
    issue = _make_issue(1, labels=["a", "b"])
    repo = _make_repo([issue])

    snap = service.fetch_issue_snapshots(repo)[0]

    # A tuple is immutable by language guarantee; combined with the frozen
    # dataclass (tested below) labels cannot be mutated or replaced.
    assert isinstance(snap.labels, tuple)


@patch("github_blog.services.github_service.Github")
def test_fetch_issue_snapshots_passes_timestamps_through(
    mock_github_class: MagicMock,
) -> None:
    service = GitHubService("fake-token")
    created = datetime(2024, 5, 1, tzinfo=timezone.utc)
    updated = datetime(2024, 6, 1, tzinfo=timezone.utc)
    issue = _make_issue(1, created_at=created, updated_at=updated)
    repo = _make_repo([issue])

    snap = service.fetch_issue_snapshots(repo)[0]

    assert snap.created_at == created
    assert snap.updated_at == updated


@patch("github_blog.services.github_service.Github")
def test_fetch_issue_snapshots_is_deterministic(
    mock_github_class: MagicMock,
) -> None:
    service = GitHubService("fake-token")
    issue = _make_issue(
        9,
        title="Same",
        body="body",
        author="alice",
        labels=["type:blog", "published"],
    )
    repo_a = _make_repo([issue])
    repo_b = _make_repo(
        [
            _make_issue(
                9,
                title="Same",
                body="body",
                author="alice",
                labels=["type:blog", "published"],
            )
        ]
    )

    assert service.fetch_issue_snapshots(repo_a) == service.fetch_issue_snapshots(
        repo_b
    )


@patch("github_blog.services.github_service.Github")
def test_fetch_issue_snapshots_leaks_no_pygithub_objects(
    mock_github_class: MagicMock,
) -> None:
    service = GitHubService("fake-token")
    issue = _make_issue(1, author="alice", labels=["type:blog"], is_pr=True)
    repo = _make_repo([issue])

    snap = service.fetch_issue_snapshots(repo)[0]

    # Only declared, plain Python fields escape the adapter boundary.
    assert {f.name for f in dataclasses.fields(snap)} == {
        "number",
        "title",
        "author",
        "body",
        "labels",
        "created_at",
        "updated_at",
        "is_pull_request",
    }
    for field in dataclasses.fields(snap):
        value = getattr(snap, field.name)
        assert not isinstance(value, MagicMock), (
            f"field {field.name!r} leaked a PyGithub object: {value!r}"
        )
    assert all(isinstance(label, str) for label in snap.labels)


@patch("github_blog.services.github_service.Github")
def test_fetch_issue_snapshots_performs_no_mutation(
    mock_github_class: MagicMock,
) -> None:
    service = GitHubService("fake-token")
    issue = _make_issue(1, labels=["type:blog"])
    repo = _make_repo([issue])

    service.fetch_issue_snapshots(repo)

    # The adapter is read-only: no Issue/repo creation, editing, labeling, or
    # publishing may occur.
    issue.edit.assert_not_called()
    issue.add_to_labels.assert_not_called()
    issue.set_labels.assert_not_called()
    issue.delete_labels.assert_not_called()
    issue.create_comment.assert_not_called()
    repo.create_issue.assert_not_called()
    repo.edit.assert_not_called()
    repo.create_label.assert_not_called()


@patch("github_blog.services.github_service.Github")
def test_to_issue_snapshot_reads_pr_identity_without_detail_request(
    mock_github_class: MagicMock,
) -> None:
    """Snapshot conversion must not trigger a per-Issue detail GET request.

    PyGithub's ``Issue.pull_request`` property calls ``_completeIfNotSet``
    which, when the ``pull_request`` key is absent from the list-response
    payload, issues a GET to the individual issue URL (N+1). This test builds
    real PyGithub ``Issue`` objects from realistic raw payloads—one where
    ``pull_request`` is absent (worst case for N+1) and one where it is present
    as a dict (PR)—and asserts that no detail request occurs during
    conversion.
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

    # Case 1: pull_request key absent from the list response.
    # Accessing issue.pull_request on this object would trigger completion.
    raw_missing = dict(
        base_raw, number=42, url="https://api.github.com/repos/o/r/issues/42"
    )
    issue_missing = PyGithubIssue(requester, {}, raw_missing)

    snap_missing = _to_issue_snapshot(issue_missing)

    requester.requestJsonAndCheck.assert_not_called()
    assert snap_missing.is_pull_request is False
    assert snap_missing.number == 42

    # Case 2: pull_request present as a dict (a real PR).
    raw_pr = dict(base_raw, number=7, url="https://api.github.com/repos/o/r/issues/7")
    raw_pr["pull_request"] = {
        "url": "https://api.github.com/repos/o/r/pulls/7",
        "html_url": "https://github.com/o/r/pull/7",
        "diff_url": "https://github.com/o/r/pull/7.diff",
        "patch_url": "https://github.com/o/r/pull/7.patch",
    }
    issue_pr = PyGithubIssue(requester, {}, raw_pr)

    snap_pr = _to_issue_snapshot(issue_pr)

    requester.requestJsonAndCheck.assert_not_called()
    assert snap_pr.is_pull_request is True
    assert snap_pr.number == 7


def test_issue_snapshot_is_frozen() -> None:
    snap = IssueSnapshot(
        number=1,
        title="t",
        author="a",
        body="b",
        labels=("x",),
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        is_pull_request=False,
    )
    # A frozen dataclass rejects field assignment at runtime; the bare type
    # ignore suppresses the static read-only-assignment diagnostic for this
    # intentional immutability probe.
    with pytest.raises(FrozenInstanceError):
        snap.number = 999  # type: ignore
    with pytest.raises(FrozenInstanceError):
        snap.labels = ("y",)  # type: ignore
