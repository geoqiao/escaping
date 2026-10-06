import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from github import Auth, Github, GithubException
from github.Issue import Issue
from github.Repository import Repository

from escaping_site.config import PlatformContext, ProfileConfig, RepositoryIdentity
from escaping_site.models.issue_snapshot import IssueSnapshot
from escaping_site.projects import ProjectEnrichment


@dataclass(frozen=True)
class PublicProfile:
    login: str
    name: str = ""
    avatar_url: str = ""
    bio: str = ""


class PagesNotReadyError(ValueError):
    """GitHub Pages cannot receive the site this build would publish."""

    def __init__(self) -> None:
        super().__init__(
            "GitHub Pages: in Settings → Pages, set Source to GitHub Actions, "
            "then run the workflow again; or set site.url in the Config to "
            "publish somewhere else"
        )


class GitHubService:
    def __init__(self, token: str) -> None:
        self.gh = Github(auth=Auth.Token(token))

    def get_repo(self, repo_name: str) -> Repository:
        return self.gh.get_repo(repo_name)

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

    def fetch_repository_identity(self, repository: str) -> RepositoryIdentity:
        repo = self.get_repo(repository)
        identity = RepositoryIdentity.model_validate(
            {
                "repository": repo.full_name,
                "owner_login": repo.owner.login,
                "owner_type": repo.owner.type,
            }
        )
        if (
            identity.repository.casefold() != repository.casefold()
            or repo.html_url.casefold() != f"https://github.com/{repository}".casefold()
        ):
            raise ValueError(
                "content repository identity does not match GitHub.com input"
            )
        return identity

    def fetch_platform_context(self, repository: str) -> PlatformContext:
        """The repository's owner and Pages address, for a build on GitHub Actions.

        Raises:
            PagesNotReadyError: Pages is off or does not deploy from Actions.
        """
        identity = self.fetch_repository_identity(repository)
        try:
            _, pages = self.gh.requester.requestJsonAndCheck(
                "GET", f"/repos/{repository}/pages"
            )
        except GithubException:
            pages = {}
        if not isinstance(pages, dict) or pages.get("build_type") != "workflow":
            raise PagesNotReadyError
        return PlatformContext.model_validate(
            {**identity.model_dump(), "pages_base_url": pages.get("html_url")}
        )

    def fetch_project_enrichment(self, repository: str) -> ProjectEnrichment:
        repo = self.get_repo(repository)
        return ProjectEnrichment(
            stars=repo.stargazers_count,
            forks=repo.forks_count,
            language=repo.language,
            topics=tuple(repo.get_topics()),
            name=repo.name,
            description=repo.description,
        )

    def fetch_public_profile(self, login: str) -> PublicProfile:
        # Only these public fields cross the boundary; no email or repo listing.
        user = self.gh.get_user(login)
        if user.login.casefold() != login.casefold():
            raise ValueError("public profile login does not match repository owner")
        profile = ProfileConfig(avatar=user.avatar_url or "", bio=user.bio or "")
        return PublicProfile(user.login, user.name or "", profile.avatar, profile.bio)


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


def read_issues_json(path: Path) -> list[IssueSnapshot]:
    """Read Issues saved from the GitHub REST API, for offline builds.

    Accepts the output of
    ``gh api --paginate --slurp 'repos/OWNER/REPO/issues?state=all&per_page=100'``
    (a list of pages) or a single list of Issue objects.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{path.name}:{exc.lineno}:{exc.colno}: not valid JSON"
        ) from None
    if not isinstance(data, list):
        raise ValueError(f"{path.name}: expected a JSON list of Issues")
    items = [
        item
        for entry in data
        for item in (entry if isinstance(entry, list) else [entry])
    ]
    snapshots = []
    for index, item in enumerate(items):
        try:
            snapshots.append(
                IssueSnapshot(
                    number=int(item["number"]),
                    title=item.get("title") or "",
                    author=(item.get("user") or {}).get("login", ""),
                    body=item.get("body") or "",
                    labels=tuple(label["name"] for label in item.get("labels", ())),
                    created_at=datetime.fromisoformat(item["created_at"]),
                    updated_at=datetime.fromisoformat(item["updated_at"]),
                    is_pull_request=item.get("pull_request") is not None,
                )
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            raise ValueError(
                f"{path.name}: item {index} is not a GitHub Issue object"
            ) from None
    return snapshots
