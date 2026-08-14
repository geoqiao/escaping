"""High-signal tests for safe candidate publication."""

from __future__ import annotations

import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from escaping.config import LocalThemeConfig, Settings
from escaping.models.issue_snapshot import IssueSnapshot
from escaping.output_staging import OutputStagingError, OutputStagingService
from escaping.site_compiler import SiteCompiler


def _snapshot(number: int, body: str, *, kind: str = "blog") -> IssueSnapshot:
    now = datetime(2026, 1, number, tzinfo=UTC)
    return IssueSnapshot(
        number,
        "Post",
        "geoqiao",
        body,
        (f"type:{kind}", "published"),
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


def test_failed_promotion_restores_previous_output(tmp_path: Path) -> None:
    service = OutputStagingService("output", tmp_path)
    final = tmp_path / "output"
    final.mkdir()
    (final / "index.html").write_text("old", encoding="utf-8")
    staging = service.create_staging_directory()
    (staging / "index.html").write_text("new", encoding="utf-8")

    real_rename = os.rename

    def fail_candidate_promotion(source: Path, destination: Path) -> None:
        if Path(source) == staging and Path(destination) == final:
            raise OSError("injected promotion failure")
        real_rename(source, destination)

    with (
        patch(
            "escaping.output_staging.os.rename",
            side_effect=fail_candidate_promotion,
        ),
        pytest.raises(OutputStagingError, match="restored previous output"),
    ):
        service.publish(staging)

    assert (final / "index.html").read_text(encoding="utf-8") == "old"
    assert (staging / "index.html").read_text(encoding="utf-8") == "new"
    assert not list(tmp_path.glob(".output.backup.*"))


def test_failed_rollback_preserves_recovery_trees_and_reports_paths(
    tmp_path: Path,
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "index.html").write_text("old", encoding="utf-8")
    real_rename = os.rename

    def fail_publication_and_rollback(source: Path, destination: Path) -> None:
        source_path = Path(source)
        destination_path = Path(destination)
        if destination_path == output and source_path.name.startswith(
            ".output.staging."
        ):
            raise OSError("injected promotion failure")
        if destination_path == output and source_path.name.startswith(
            ".output.backup."
        ):
            raise OSError("injected rollback failure")
        real_rename(source, destination)

    with patch(
        "escaping.output_staging.os.rename",
        side_effect=fail_publication_and_rollback,
    ):
        result = SiteCompiler(
            "unused",
            "geoqiao/site",
            _settings(),
            config_root=tmp_path,
            github_service=_FakeGitHub(
                [
                    _snapshot(
                        1,
                        '---\ndescription: About.\ncreated_date: "2026-01-01"'
                        "\n---\n\nAbout.",
                        kind="about",
                    )
                ]
            ),
        ).generate()

    assert not result.success
    staging = next(tmp_path.glob(".output.staging.*"))
    backup = next(tmp_path.glob(".output.backup.*"))
    assert not output.exists()
    assert (staging / "index.html").exists()
    assert (backup / "index.html").read_text(encoding="utf-8") == "old"
    diagnostic = next(
        item
        for item in result.diagnostics
        if item.code == "BUILD_FAILED" and "rollback" in item.message.lower()
    )
    assert str(output) in diagnostic.message
    assert str(staging) in diagnostic.message
    assert str(backup) in diagnostic.message


def test_backup_cleanup_failure_warns_after_successful_publication(
    tmp_path: Path,
) -> None:
    service = OutputStagingService("output", tmp_path)
    final = tmp_path / "output"
    final.mkdir()
    (final / "index.html").write_text("old", encoding="utf-8")
    staging = service.create_staging_directory()
    (staging / "index.html").write_text("new", encoding="utf-8")

    with patch(
        "escaping.output_staging.shutil.rmtree",
        side_effect=OSError("injected cleanup failure"),
    ):
        diagnostics = service.publish(staging)

    backup = next(tmp_path.glob(".output.backup.*"))
    assert (final / "index.html").read_text(encoding="utf-8") == "new"
    assert (backup / "index.html").read_text(encoding="utf-8") == "old"
    assert [item.code for item in diagnostics] == ["BACKUP_CLEANUP_FAILED"]
    assert diagnostics[0].severity == "warning"
    assert str(backup) in diagnostics[0].message


def test_cleanup_rejects_unregistered_candidate(tmp_path: Path) -> None:
    service = OutputStagingService("output", tmp_path)
    staging = service.create_staging_directory()
    service.cleanup(staging)
    assert not staging.exists()

    external = tmp_path / "external"
    external.mkdir()
    with pytest.raises(OutputStagingError, match="unregistered"):
        service.cleanup(external)


def test_publish_rejects_foreign_sibling_staging_path(tmp_path: Path) -> None:
    service = OutputStagingService("output", tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    (output / "sentinel.txt").write_text("final", encoding="utf-8")

    foreign = tmp_path / ".output.staging.0123456789ab"
    foreign.mkdir()
    (foreign / "sentinel.txt").write_text("foreign", encoding="utf-8")

    with pytest.raises(OutputStagingError, match="unregistered"):
        service.publish(foreign)

    assert output.is_dir()
    assert (output / "sentinel.txt").read_text(encoding="utf-8") == "final"
    assert foreign.is_dir()
    assert (foreign / "sentinel.txt").read_text(encoding="utf-8") == "foreign"


def test_publish_and_cleanup_reject_staging_replaced_by_symlink(
    tmp_path: Path,
) -> None:
    service = OutputStagingService("output", tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    (output / "sentinel.txt").write_text("final", encoding="utf-8")

    staging = service.create_staging_directory()
    staging.rmdir()
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    (decoy / "sentinel.txt").write_text("decoy", encoding="utf-8")
    staging.symlink_to(decoy, target_is_directory=True)

    with pytest.raises(OutputStagingError, match="symlink"):
        service.publish(staging)
    with pytest.raises(OutputStagingError):
        service.cleanup(staging)

    assert output.is_dir()
    assert (output / "sentinel.txt").read_text(encoding="utf-8") == "final"
    assert decoy.is_dir()
    assert (decoy / "sentinel.txt").read_text(encoding="utf-8") == "decoy"


def test_publish_reports_concurrent_disappearance_during_backup_reservation(
    tmp_path: Path,
) -> None:
    service = OutputStagingService("output", tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    staging = service.create_staging_directory()

    def disappear(path: Path) -> tuple[int, int]:
        if path == output:
            shutil.rmtree(output)
            raise FileNotFoundError("injected concurrent disappearance")
        stat = path.stat()
        return stat.st_dev, stat.st_ino

    with (
        patch("escaping.output_staging._st_identity", side_effect=disappear),
        pytest.raises(OutputStagingError, match="concurrent local builds"),
    ):
        service.publish(staging)

    assert not output.exists()


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


def test_template_error_preserves_existing_output_and_cleans_staging(
    tmp_path: Path,
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    sentinel = output / "index.html"
    sentinel.write_text("old", encoding="utf-8")

    local_theme = tmp_path / "broken-theme"
    shutil.copytree(
        Path(__file__).parent.parent / "src/escaping/themes/geoqiao.me",
        local_theme,
    )
    home_template = local_theme / "home.html"
    home_template.write_text(
        home_template.read_text(encoding="utf-8").replace(
            "{% endblock %}", "{{ missing_template_value }}\n{% endblock %}", 1
        ),
        encoding="utf-8",
    )
    settings = _settings().model_copy(
        update={
            "theme": LocalThemeConfig(name="broken-theme", path=Path("broken-theme"))
        }
    )

    result = SiteCompiler(
        "unused",
        "geoqiao/site",
        settings,
        config_root=tmp_path,
        github_service=_FakeGitHub(
            [
                _snapshot(
                    1,
                    '---\ndescription: About.\ncreated_date: "2026-01-01"'
                    "\n---\n\nAbout.",
                    kind="about",
                )
            ]
        ),
    ).generate()

    assert not result.success
    assert any(
        diagnostic.code == "TEMPLATE_RENDER_FAILED" for diagnostic in result.diagnostics
    )
    assert sentinel.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.glob(".output.staging.*")) == []
