"""High-signal tests for safe candidate publication."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from escaping_site.config import Settings
from escaping_site.models.issue_snapshot import IssueSnapshot
from escaping_site.output_staging import (
    OUTPUT_MARKER,
    OutputStagingError,
    OutputStagingService,
)
from escaping_site.site_compiler import SiteCompiler


def _snapshot(number: int, body: str, *, kind: str = "blog") -> IssueSnapshot:
    now = datetime(2026, 1, number, tzinfo=UTC)
    return IssueSnapshot(
        number, "Post", "geoqiao", body, (f"type:{kind}", "published"), now, now, False
    )


_ABOUT = _snapshot(1, "About.", kind="about")


def _settings(**overrides: object) -> Settings:
    return Settings.model_validate(
        {
            "github": {"repo": "geoqiao/site", "allowed_authors": ["geoqiao"]},
            "site": {
                "title": "geoqiao.me",
                "author": "geoqiao",
                "url": "https://geoqiao.me/",
            },
            "about": {"issue_number": 1},
            **overrides,
        }
    )


def _compiler(
    tmp_path: Path, snapshots: list[IssueSnapshot], settings: Settings | None = None
) -> SiteCompiler:
    return SiteCompiler(
        settings or _settings(), config_root=tmp_path, issues=lambda: snapshots
    )


def _tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _owned_output(tmp_path: Path, text: str = "old") -> Path:
    """An output directory an earlier build published."""
    output = tmp_path / "output"
    output.mkdir()
    (output / OUTPUT_MARKER).write_text("", encoding="utf-8")
    (output / "index.html").write_text(text, encoding="utf-8")
    return output


def test_publish_marks_its_output_and_replaces_only_its_own_tree(
    tmp_path: Path,
) -> None:
    service = OutputStagingService("output", tmp_path)
    staging = service.create_staging_directory()
    assert (staging / OUTPUT_MARKER).is_file()
    (staging / "index.html").write_text("new", encoding="utf-8")
    service.publish(staging)

    final = tmp_path / "output"
    assert (final / "index.html").read_text(encoding="utf-8") == "new"
    assert (final / OUTPUT_MARKER).is_file()

    (final / "stale.txt").write_text("old", encoding="utf-8")
    replacement = service.create_staging_directory()
    (replacement / "index.html").write_text("newer", encoding="utf-8")
    service.publish(replacement)

    assert (final / "index.html").read_text(encoding="utf-8") == "newer"
    assert not (final / "stale.txt").exists()
    assert not list(tmp_path.glob(".output.*"))


@pytest.mark.parametrize(
    ("prepare", "problem"),
    [
        (lambda output: None, None),
        (lambda output: output.mkdir(), None),
        (lambda output: _owned_output(output.parent), None),
        (
            lambda output: (output.mkdir(), (output / "notes.md").write_text("mine")),
            "contains files escaping did not create",
        ),
        (lambda output: output.write_text("mine"), "is a file"),
    ],
    ids=["missing", "empty", "owned", "unowned", "file"],
)
def test_only_missing_empty_or_owned_output_can_be_replaced(
    tmp_path: Path, prepare: Callable[[Path], object], problem: str | None
) -> None:
    output = tmp_path / "output"
    prepare(output)
    before = _tree(output) if output.is_dir() else None
    service = OutputStagingService("output", tmp_path)
    staging = service.create_staging_directory()
    if problem is None:
        service.check_replaceable()
        service.publish(staging)
        assert (output / OUTPUT_MARKER).is_file()
        return
    with pytest.raises(OutputStagingError, match=problem):
        service.check_replaceable()
    with pytest.raises(OutputStagingError, match=problem):
        service.publish(staging)
    if before is not None:
        assert _tree(output) == before
    else:
        assert output.read_text(encoding="utf-8") == "mine"


def test_failed_promotion_restores_previous_output(tmp_path: Path) -> None:
    service = OutputStagingService("output", tmp_path)
    final = _owned_output(tmp_path)
    staging = service.create_staging_directory()
    (staging / "index.html").write_text("new", encoding="utf-8")

    real_rename = os.rename

    def fail_candidate_promotion(source: Path, destination: Path) -> None:
        if Path(source) == staging and Path(destination) == final:
            raise OSError("injected promotion failure")
        real_rename(source, destination)

    with (
        patch(
            "escaping_site.output_staging.os.rename",
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
    output = _owned_output(tmp_path)
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
        "escaping_site.output_staging.os.rename",
        side_effect=fail_publication_and_rollback,
    ):
        result = _compiler(tmp_path, [_ABOUT]).generate()

    assert not result.success
    staging = next(tmp_path.glob(".output.staging.*"))
    backup = next(tmp_path.glob(".output.backup.*"))
    assert not output.exists()
    assert (staging / "index.html").exists()
    assert (backup / "index.html").read_text(encoding="utf-8") == "old"
    diagnostic = next(
        item
        for item in result.diagnostics
        if item.code == "PUBLISH_FAILED" and "rollback" in item.message.lower()
    )
    assert str(output) in diagnostic.message
    assert str(staging) in diagnostic.message
    assert str(backup) in diagnostic.message


def test_backup_cleanup_failure_warns_after_successful_publication(
    tmp_path: Path,
) -> None:
    service = OutputStagingService("output", tmp_path)
    final = _owned_output(tmp_path)
    staging = service.create_staging_directory()
    (staging / "index.html").write_text("new", encoding="utf-8")

    with patch(
        "escaping_site.output_staging.shutil.rmtree",
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
    shutil.rmtree(staging)
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    (decoy / "sentinel.txt").write_text("decoy", encoding="utf-8")
    staging.symlink_to(decoy, target_is_directory=True)

    with pytest.raises(OutputStagingError, match="symlink"):
        service.publish(staging)
    with pytest.raises(OutputStagingError, match="unregistered"):
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
        patch("escaping_site.output_staging._st_identity", side_effect=disappear),
        pytest.raises(OutputStagingError, match="concurrent local builds"),
    ):
        service.publish(staging)

    assert not output.exists()


def _broken_theme(tmp_path: Path) -> dict[str, Any]:
    """A Theme that extends Quiet and fails only while rendering."""
    theme = tmp_path / "theme"
    theme.mkdir()
    (theme / "theme.yaml").write_text("api: 4\nextends: quiet\n", encoding="utf-8")
    (theme / "about.html").write_text("{{ page.no_such_field }}", encoding="utf-8")
    return {"theme": {"use": "./theme"}}


@pytest.mark.parametrize(
    ("change", "code"),
    [
        # A broken configured About stops the build.
        (
            lambda: ([_snapshot(1, "---\nslug: x\n---\nAbout.", kind="about")], {}),
            "SLUG_FORBIDDEN",
        ),
        # Content that renders but links to a file that does not exist.
        (
            lambda: ([_snapshot(1, "[CV](/cv.pdf)", kind="about")], {}),
            "BROKEN_INTERNAL_LINK",
        ),
        (lambda: ([_ABOUT], None), "TEMPLATE_RENDER_FAILED"),
        (lambda: (None, {}), "FETCH_FAILED"),
    ],
    ids=["content", "validation", "template", "fetch"],
)
def test_a_failed_build_leaves_the_previous_output_unchanged(
    tmp_path: Path,
    change: Callable[[], tuple[list[IssueSnapshot] | None, dict[str, Any] | None]],
    code: str,
) -> None:
    assert _compiler(tmp_path, [_ABOUT, _snapshot(2, "Post.")]).generate().success
    output = tmp_path / "output"
    before = _tree(output)
    snapshots, overrides = change()
    settings = _settings(
        **(_broken_theme(tmp_path) if overrides is None else overrides)
    )

    def issues() -> list[IssueSnapshot]:
        if snapshots is None:
            raise RuntimeError("network down")
        return snapshots

    result = SiteCompiler(settings, config_root=tmp_path, issues=issues).generate()

    assert not result.success
    assert code in {d.code for d in result.diagnostics if d.severity == "error"}
    assert _tree(output) == before
    assert not list(tmp_path.glob(".output.*"))
