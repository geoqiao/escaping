"""High-signal tests for safe candidate publication."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from escaping.config import Settings
from escaping.models.issue_snapshot import IssueSnapshot
from escaping.output_staging import OutputStagingError, OutputStagingService
from escaping.site_compiler import SiteCompiler


def _snapshot(number: int, body: str) -> IssueSnapshot:
    now = datetime(2026, 1, number, tzinfo=timezone.utc)
    return IssueSnapshot(
        number,
        "Post",
        "geoqiao",
        body,
        ("type:blog", "published"),
        now,
        now,
        False,
    )


class _FakeGitHub:
    def __init__(self, snapshots: list[IssueSnapshot]) -> None:
        self.snapshots = snapshots

    def get_repo(self, name: str) -> object:
        return object()

    def fetch_issue_snapshots(self, repo: object) -> list[IssueSnapshot]:
        return self.snapshots


def _settings() -> Settings:
    return Settings.model_validate(
        {
            "github": {"repo": "geoqiao/site", "allowed_authors": ["geoqiao"]},
            "site": {
                "title": "geoqiao.me",
                "author": "geoqiao",
                "url": "https://geoqiao.me/",
            },
            "about": {"issue_number": 1},
            "paths": {"output": "output"},
            "security": {"token_env": "TOKEN"},
        }
    )


def test_publish_replaces_existing_tree_without_partial_output(tmp_path: Path) -> None:
    service = OutputStagingService("output", tmp_path)
    staging = service.create_staging_directory()
    (staging / "index.html").write_text("new", encoding="utf-8")
    service.publish(staging)

    final = tmp_path / "output"
    assert (final / "index.html").read_text(encoding="utf-8") == "new"

    (final / "stale.txt").write_text("old", encoding="utf-8")
    replacement = service.create_staging_directory()
    (replacement / "index.html").write_text("newer", encoding="utf-8")
    service.publish(replacement)

    assert (final / "index.html").read_text(encoding="utf-8") == "newer"
    assert not (final / "stale.txt").exists()


def test_failed_exchange_leaves_final_and_candidate_unchanged(tmp_path: Path) -> None:
    service = OutputStagingService("output", tmp_path)
    final = tmp_path / "output"
    final.mkdir()
    (final / "index.html").write_text("old", encoding="utf-8")
    staging = service.create_staging_directory()
    (staging / "index.html").write_text("new", encoding="utf-8")

    with (
        patch("escaping.output_staging._atomic_swap", side_effect=OSError("no swap")),
        pytest.raises(OutputStagingError, match="final output unchanged"),
    ):
        service.publish(staging)

    assert (final / "index.html").read_text(encoding="utf-8") == "old"
    assert (staging / "index.html").read_text(encoding="utf-8") == "new"


def test_cleanup_rejects_unregistered_candidate(tmp_path: Path) -> None:
    service = OutputStagingService("output", tmp_path)
    staging = service.create_staging_directory()
    service.cleanup(staging)
    assert not staging.exists()

    external = tmp_path / "external"
    external.mkdir()
    with pytest.raises(OutputStagingError, match="unregistered"):
        service.cleanup(external)


def test_strict_compiler_failure_preserves_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    sentinel = output / "index.html"
    sentinel.write_text("old", encoding="utf-8")

    result = SiteCompiler(
        "unused",
        "geoqiao/site",
        _settings(),
        config_root=tmp_path,
        github_service=_FakeGitHub([_snapshot(1, "not front matter")]),
    ).generate()

    assert not result.success
    assert sentinel.read_text(encoding="utf-8") == "old"
    assert not list(tmp_path.glob(".output.staging.*"))
