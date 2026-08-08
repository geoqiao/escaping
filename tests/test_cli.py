from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from escaping.cli import run_cli
from escaping.config import Settings
from escaping.models.issue_snapshot import IssueSnapshot
from escaping.projects import ProjectEnrichment
from escaping.site_compiler import SiteCompiler


def _settings(*, projects: list[dict[str, object]] | None = None) -> Settings:
    data: dict[str, object] = {
        "github": {"repo": "geoqiao/site", "allowed_authors": ["geoqiao"]},
        "site": {
            "title": "geoqiao.me",
            "author": "geoqiao",
            "url": "https://geoqiao.me/",
            "navigation": {"items": [{"name": "Blog", "url": "/blog/"}]},
        },
        "about": {"issue_number": 10},
        "security": {"token_env": "TOKEN"},
        "paths": {"output": "output"},
    }
    if projects is not None:
        data["projects"] = projects
    return Settings.model_validate(data)


def _snapshot(number: int, kind: str, body: str) -> IssueSnapshot:
    now = datetime(2026, 1, number, tzinfo=UTC)
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


def test_cli_loads_an_explicit_config_and_reports_its_missing_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site = tmp_path / "site"
    site.mkdir()
    config = site / "config.yaml"
    config.write_text(
        """github:\n  repo: geoqiao/site\n  allowed_authors: [geoqiao]\nsite:\n  title: Site\n  author: geoqiao\n  url: https://example.com/\nabout:\n  issue_number: 1\nsecurity:\n  token_env: CLI_TEST_TOKEN\n""",
        encoding="utf-8",
    )
    unrelated_cwd = tmp_path / "elsewhere"
    unrelated_cwd.mkdir()
    monkeypatch.chdir(unrelated_cwd)
    monkeypatch.delenv("CLI_TEST_TOKEN", raising=False)
    monkeypatch.setattr(sys, "argv", ["escpe", "--config", str(config)])

    with pytest.raises(SystemExit) as exc_info:
        run_cli()

    assert exc_info.value.code == 1


def test_strict_cli_generates_directory_routes_and_seo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    unrelated_cwd = tmp_path / "elsewhere"
    unrelated_cwd.mkdir()
    sentinel = tmp_path / "outside-sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    monkeypatch.chdir(unrelated_cwd)
    output = repo / "output"
    result = SiteCompiler(
        "unused",
        "geoqiao/site",
        _settings(),
        config_root=repo,
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


def test_project_enrichment_warning_reaches_build_result(tmp_path: Path) -> None:
    def enrich(_repository: str) -> ProjectEnrichment:
        raise RuntimeError("token=super-secret")

    result = SiteCompiler(
        "unused",
        "geoqiao/site",
        _settings(
            projects=[
                {
                    "slug": "fallback",
                    "title": "Fallback",
                    "repository": "geoqiao/fallback",
                    "summary": "Fallback project.",
                    "fallback_metadata": {"stars": 7},
                }
            ]
        ),
        config_root=tmp_path,
        github_service=_FakeGitHub(_valid_snapshots()),
        project_enricher=enrich,
    ).generate()

    assert result.success
    warning = next(
        diagnostic
        for diagnostic in result.diagnostics
        if diagnostic.code == "PROJECT_ENRICHMENT_FAILED"
    )
    assert warning.severity == "warning"
    assert warning.field == "projects.fallback"
    assert "token=super-secret" not in warning.message


def test_content_error_preserves_existing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
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
        config_root=repo,
        github_service=_FakeGitHub(bad),
    ).generate()
    assert not result.success
    assert sentinel.read_text(encoding="utf-8") == "old"
    assert outside_sentinel.read_text(encoding="utf-8") == "keep"
