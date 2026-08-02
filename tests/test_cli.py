from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from github_blog.config import Settings
from github_blog.models.issue_snapshot import IssueSnapshot
from github_blog.site_compiler import SiteCompiler

_ROOT = Path(__file__).parent.parent


def _settings() -> Settings:
    return Settings.model_validate(
        {
            "github": {"repo": "geoqiao/site", "allowed_authors": ["geoqiao"]},
            "site": {
                "title": "geoqiao.me",
                "author": "geoqiao",
                "url": "https://geoqiao.me/",
                "navigation": {"items": [{"name": "Blog", "url": "/blog/"}]},
            },
            "about": {"issue_number": 10},
            "security": {"token_env": "TOKEN"},
            "paths": {"output": "output", "theme": "geoqiao.me"},
        }
    )


def _snapshot(number: int, kind: str, body: str) -> IssueSnapshot:
    now = datetime(2026, 1, number, tzinfo=timezone.utc)
    return IssueSnapshot(
        number,
        {"blog": "Post", "idea": "Idea", "about": "About"}[kind],
        "geoqiao",
        body,
        (f"type:{kind}", "published"),
        now,
        now,
        False,
    )


def _valid_snapshots() -> list[IssueSnapshot]:
    return [
        _snapshot(
            1,
            "blog",
            '---\nslug: post\ndescription: A post.\ncreated_date: "2026-01-01"\n---\n\nBody.',
        ),
        _snapshot(
            2,
            "idea",
            '---\ndescription: An idea.\ncreated_date: "2026-01-02"\n---\n\nIdea.',
        ),
        _snapshot(
            10,
            "about",
            '---\ndescription: About.\ncreated_date: "2026-01-03"\n---\n\nAbout.',
        ),
    ]


class _FakeGitHub:
    def __init__(self, snapshots: list[IssueSnapshot]) -> None:
        self.snapshots = snapshots

    def get_repo(self, name: str) -> object:
        return object()

    def fetch_issue_snapshots(self, repo: object) -> list[IssueSnapshot]:
        return self.snapshots


def test_strict_cli_generates_directory_routes_and_seo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    shutil.copytree(
        _ROOT / "templates" / "geoqiao.me", repo / "templates" / "geoqiao.me"
    )
    sentinel = tmp_path / "outside-sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    monkeypatch.chdir(repo)
    output = repo / "output"
    result = SiteCompiler(
        "unused",
        "geoqiao/site",
        _settings(),
        github_service=_FakeGitHub(_valid_snapshots()),
    ).generate()
    assert result.success
    assert (output / "index.html").exists()
    assert (output / "blog" / "post" / "index.html").exists()
    assert (output / "ideas" / "2" / "index.html").exists()
    assert (output / "about" / "index.html").exists()
    assert (output / "atom.xml").exists()
    assert "https://geoqiao.me" in (output / "sitemap.xml").read_text()
    assert not (output / "blog" / "post.html").exists()
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_content_error_preserves_existing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    shutil.copytree(
        _ROOT / "templates" / "geoqiao.me", repo / "templates" / "geoqiao.me"
    )
    outside_sentinel = tmp_path / "outside-sentinel.txt"
    outside_sentinel.write_text("keep", encoding="utf-8")
    monkeypatch.chdir(repo)
    output = repo / "output"
    output.mkdir()
    sentinel = output / "index.html"
    sentinel.write_text("old", encoding="utf-8")
    bad = _valid_snapshots()
    bad[0] = _snapshot(1, "blog", "not front matter")
    result = SiteCompiler(
        "unused",
        "geoqiao/site",
        _settings(),
        github_service=_FakeGitHub(bad),
    ).generate()
    assert not result.success
    assert sentinel.read_text(encoding="utf-8") == "old"
    assert outside_sentinel.read_text(encoding="utf-8") == "keep"
