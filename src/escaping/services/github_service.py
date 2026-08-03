import structlog
from github import Auth, Github
from github.Issue import Issue
from github.Repository import Repository
from tenacity import retry, stop_after_attempt, wait_exponential

from escaping.models.issue_snapshot import IssueSnapshot

logger = structlog.get_logger()


class GitHubService:
    def __init__(self, token: str) -> None:
        self.gh = self._login(token)

    def _login(self, token: str) -> Github:
        try:
            # Compatibility with different PyGithub versions
            if hasattr(Auth, "Token"):
                return Github(auth=Auth.Token(token))
            return Github(token)
        except Exception as e:
            logger.error("github_login_failed", error=str(e))
            raise

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def get_repo(self, repo_name: str) -> Repository:
        return self.gh.get_repo(repo_name)

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def fetch_issue_snapshots(self, repo: Repository) -> list[IssueSnapshot]:
        """Fetch open and closed Issues (state=all) as immutable snapshots.

        This is the read-only ingestion seam: it queries both open and closed
        Issues, converts each into an immutable ``IssueSnapshot`` containing
        only compiler-relevant plain values, and performs no mutation. Pull
        Request identity is recorded (``is_pull_request``) so the compiler can
        exclude PRs during selection; this method does not filter them.
        """
        issues = repo.get_issues(state="all")  # type: ignore[union-attr]
        return [_to_issue_snapshot(issue) for issue in issues]


def _to_issue_snapshot(issue: Issue) -> IssueSnapshot:
    """Convert a PyGithub Issue into an immutable IssueSnapshot.

    The only place PyGithub objects are read; the returned value contains only
    plain Python types so no PyGithub object crosses the adapter boundary.
    """
    labels = issue.labels or ()
    return IssueSnapshot(
        number=issue.number,
        title=issue.title or "",
        author=issue.user.login if issue.user else "",
        body=issue.body or "",
        labels=tuple(label.name for label in labels),
        created_at=issue.created_at,
        updated_at=issue.updated_at,
        is_pull_request=_is_pull_request(issue),
    )


def _is_pull_request(issue: Issue) -> bool:
    """Determine PR identity from list-response metadata without completion.

    PyGithub's ``Issue.pull_request`` property calls ``_completeIfNotSet``;
    when the ``pull_request`` key is absent from the list-response payload the
    property issues a per-Issue detail GET request (N+1). Reading the raw
    payload (``_rawData``) directly avoids that lazy completion entirely while
    preserving the same True/False semantics for the normal list response.
    """
    raw = getattr(issue, "_rawData", None) or {}
    return raw.get("pull_request") is not None
