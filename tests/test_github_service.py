from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from escaping.services.github_service import GitHubService


def test_github_service_login_uses_supported_auth_api() -> None:
    with (
        patch("escaping.services.github_service.Github") as github,
        patch("escaping.services.github_service.Auth") as auth,
    ):
        auth.Token = MagicMock()
        GitHubService("fake-token")
        auth.Token.assert_called_once_with("fake-token")
        github.assert_called_once()


def test_fetch_issue_snapshots_queries_all_states_and_isolates_fields() -> None:
    with patch("escaping.services.github_service.Github"):
        issue = MagicMock()
        issue.number = 7
        issue.title = "Title"
        issue.body = "Body"
        issue.user.login = "geoqiao"
        issue.labels = [MagicMock(name="ignored")]
        issue.labels[0].name = "published"
        issue.created_at = datetime(2026, 1, 1, tzinfo=UTC)
        issue.updated_at = issue.created_at
        issue._rawData = {"pull_request": {"url": "x"}}
        repo = MagicMock()
        repo.get_issues.return_value = [issue]
        snapshots = GitHubService("fake-token").fetch_issue_snapshots(repo)
        repo.get_issues.assert_called_once_with(state="all")
        assert snapshots[0].number == 7
        assert snapshots[0].labels == ("published",)
        assert snapshots[0].is_pull_request
