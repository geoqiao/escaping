"""Tests for Ticket 03: stage output without risking the current site.

The pre-agreed seam is a public output staging/publishing interface plus
BlogGenerator integration exercised with injected collaborators and filesystem
assertions.

Covered behaviours:
- BuildResult / Diagnostic structured return (no sys.exit in core code).
- BasicArtifactValidator interface (Ticket 19 will deepen).
- OutputStagingService: staging dir creation, atomic publish, cleanup.
- BlogGenerator.generate() returns BuildResult, uses staging, preserves
  previous output byte-for-byte on fetch/render/validation failures.
- run_cli() maps BuildResult failure to exit status.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from github_blog.build_result import BuildResult, Diagnostic
from github_blog.config import Settings
from github_blog.output_safety import OutputContainmentError
from github_blog.output_staging import (
    BasicArtifactValidator,
    OutputStagingError,
    OutputStagingService,
    _st_identity,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_issue(
    number: int,
    title: str,
    body: str = "body",
    labels: list[str] | None = None,
) -> MagicMock:
    issue = MagicMock()
    issue.number = number
    issue.title = title
    issue.body = body
    label_mocks: list[MagicMock] = []
    if labels:
        for label in labels:
            m = MagicMock()
            m.name = label
            label_mocks.append(m)
    issue.labels = label_mocks
    issue.created_at = datetime(2024, 1, number, tzinfo=timezone.utc)
    issue.updated_at = datetime(2024, 1, number, tzinfo=timezone.utc)
    return issue


def _make_settings(tmp_path: Path, output: str = "output") -> Settings:
    """Create a real Settings from a minimal YAML config."""
    config = f"""
github:
  repo: user/repo
  allowed_authors:
    - user
site:
  title: Test Blog
  url: https://example.com/
  author: Test
about:
  issue_number: 1
security:
  token_env: G_T
paths:
  output: {output}
  theme: Escape1
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config)
    return Settings.load_from_yaml(config_path)


def _hash_directory(path: Path) -> str:
    """Return a deterministic SHA-256 of all files in *path*."""
    hasher = hashlib.sha256()
    for file_path in sorted(path.rglob("*")):
        if file_path.is_file():
            rel = file_path.relative_to(path)
            hasher.update(str(rel).encode())
            hasher.update(file_path.read_bytes())
    return hasher.hexdigest()


def _create_previous_output(output_dir: Path) -> None:
    """Create a known previous output tree for preservation tests."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "index.html").write_text("old index", encoding="utf-8")
    (output_dir / "blog").mkdir(exist_ok=True)
    (output_dir / "blog" / "old-post.html").write_text("old post", encoding="utf-8")
    (output_dir / "marker.txt").write_text("survive", encoding="utf-8")


def _setup_minimal_theme(tmp_path: Path) -> None:
    """Create a minimal theme directory so _copy_theme_assets succeeds.

    The real templates live in the project root; tests that chdir into
    tmp_path need a theme directory reachable from the new CWD.
    """
    theme_dir = tmp_path / "templates" / "Escape1"
    theme_dir.mkdir(parents=True)


def _assert_no_staging_dirs(parent: Path) -> None:
    """Assert no leftover staging directories exist under *parent*."""
    leftovers = [p for p in parent.iterdir() if ".staging." in p.name]
    assert not leftovers, f"Leftover staging directories: {leftovers}"


def _create_staging_and_return(tmp_path: Path) -> Path:
    """Create a real staging dir under tmp_path and return it.

    Used by tests that inject a partial-mock OutputStagingService but
    still need a real filesystem staging directory for rendering.
    """
    import uuid

    staging = tmp_path / f".output.staging.{uuid.uuid4().hex[:12]}"
    staging.mkdir(parents=True, exist_ok=False)
    return staging


def _make_fake_github_service(
    issues: list[MagicMock] | None = None,
) -> MagicMock:
    """Return a MagicMock GitHubService that returns *issues*."""
    gh = MagicMock()
    gh.get_repo.return_value = MagicMock()
    gh.get_user_issues.return_value = issues or []
    return gh


def _make_failing_github_service() -> MagicMock:
    """Return a MagicMock GitHubService that raises on get_repo."""
    gh = MagicMock()
    gh.get_repo.side_effect = RuntimeError("GitHub API error")
    return gh


def _make_fake_render_service() -> MagicMock:
    """Return a MagicMock RenderService returning fixed strings."""
    render = MagicMock()
    render.markdown_to_html.return_value = "<p>body</p>"
    render.render_post.return_value = "<html><body>body</body></html>"
    render.render_index.return_value = "<html><body>index</body></html>"
    render.render_home.return_value = "<html><body>home</body></html>"
    render.render_tag_page.return_value = "<html><body>tag</body></html>"
    render.generate_rss.return_value = '<?xml version="1.0"?><feed></feed>'
    render.render_sitemap.return_value = '<?xml version="1.0"?><urlset></urlset>'
    render.render_robots.return_value = "User-agent: *\nDisallow:"
    render.render_about.return_value = "<html><body>about</body></html>"
    render.render_tags_page.return_value = "<html><body>tags</body></html>"
    return render


def _make_failing_render_service() -> MagicMock:
    """Return a MagicMock RenderService that fails on render_post."""
    render = _make_fake_render_service()
    render.render_post.side_effect = RuntimeError("Render failed for testing")
    return render


# ---------------------------------------------------------------------------
# BuildResult / Diagnostic
# ---------------------------------------------------------------------------


class TestBuildResult:
    def test_success_result(self) -> None:
        result = BuildResult(success=True)
        assert result.success is True
        assert result.diagnostics == ()

    def test_failure_result_with_diagnostics(self) -> None:
        diag = Diagnostic(
            severity="error",
            code="FETCH_FAILED",
            message="boom",
        )
        result = BuildResult(success=False, diagnostics=(diag,))
        assert result.success is False
        assert len(result.diagnostics) == 1
        assert result.diagnostics[0].code == "FETCH_FAILED"

    def test_diagnostic_optional_fields_default_none(self) -> None:
        diag = Diagnostic(severity="error", code="X", message="m")
        assert diag.issue_number is None
        assert diag.field is None

    def test_diagnostic_with_issue_and_field(self) -> None:
        diag = Diagnostic(
            severity="warning",
            code="X",
            message="m",
            issue_number=42,
            field="slug",
        )
        assert diag.issue_number == 42
        assert diag.field == "slug"

    def test_build_result_is_frozen(self) -> None:
        from dataclasses import FrozenInstanceError

        result = BuildResult(success=True)
        with pytest.raises(FrozenInstanceError):
            result.success = False  # type: ignore

    def test_diagnostic_rejects_invalid_severity(self) -> None:
        """Diagnostic.severity must be 'error' or 'warning'."""
        with pytest.raises(ValueError, match="severity"):
            Diagnostic(severity="info", code="X", message="m")

    def test_diagnostic_accepts_error_and_warning(self) -> None:
        for sev in ("error", "warning"):
            d = Diagnostic(severity=sev, code="X", message="m")
            assert d.severity == sev


# ---------------------------------------------------------------------------
# BasicArtifactValidator
# ---------------------------------------------------------------------------


class TestBasicArtifactValidator:
    def test_valid_artifacts_pass(self, tmp_path: Path) -> None:
        (tmp_path / "index.html").write_text("ok", encoding="utf-8")
        settings = _make_settings(tmp_path)
        validator = BasicArtifactValidator(settings=settings)
        diagnostics = validator.validate(tmp_path)
        assert diagnostics == []

    def test_missing_index_html_fails(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        validator = BasicArtifactValidator(settings=settings)
        diagnostics = validator.validate(tmp_path)
        assert len(diagnostics) == 1
        assert diagnostics[0].severity == "error"
        assert diagnostics[0].code == "MISSING_REQUIRED_ARTIFACT"

    def test_empty_candidate_dir_fails(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        validator = BasicArtifactValidator(settings=settings)
        diagnostics = validator.validate(tmp_path)
        assert any(d.code == "MISSING_REQUIRED_ARTIFACT" for d in diagnostics)

    def test_directory_named_as_artifact_fails(self, tmp_path: Path) -> None:
        """A directory named ``index.html`` must not pass artifact validation.

        ``is_file()`` is used so that a directory masquerading as a
        required artifact is rejected.
        """
        (tmp_path / "index.html").mkdir()
        settings = _make_settings(tmp_path)
        validator = BasicArtifactValidator(settings=settings)
        diagnostics = validator.validate(tmp_path)
        assert any(d.code == "MISSING_REQUIRED_ARTIFACT" for d in diagnostics)


# ---------------------------------------------------------------------------
# OutputStagingService
# ---------------------------------------------------------------------------


class TestOutputStagingService:
    def test_create_staging_directory_under_output_parent(self, tmp_path: Path) -> None:
        svc = OutputStagingService("output", tmp_path)
        staging = svc.create_staging_directory()
        assert staging.exists()
        assert staging.is_dir()
        # Staging is a sibling of output (same parent).
        assert staging.parent == (tmp_path / "output").parent

    def test_create_staging_directory_within_boundary(self, tmp_path: Path) -> None:
        svc = OutputStagingService("output", tmp_path)
        staging = svc.create_staging_directory()
        assert staging.resolve().relative_to(tmp_path.resolve())

    def test_create_staging_directory_unique_names(self, tmp_path: Path) -> None:
        svc = OutputStagingService("output", tmp_path)
        a = svc.create_staging_directory()
        b = svc.create_staging_directory()
        assert a != b
        assert a.exists()
        assert b.exists()

    def test_publish_to_empty_output(self, tmp_path: Path) -> None:
        svc = OutputStagingService("output", tmp_path)
        staging = svc.create_staging_directory()
        (staging / "index.html").write_text("new", encoding="utf-8")

        svc.publish(staging)

        final = tmp_path / "output"
        assert final.exists()
        assert (final / "index.html").read_text() == "new"
        # Staging directory is gone (renamed to output).
        assert not staging.exists()
        # Staging is deregistered after successful rename.
        assert staging.resolve() not in svc._registered_staging

    def test_publish_replaces_existing_output(self, tmp_path: Path) -> None:
        svc = OutputStagingService("output", tmp_path)
        final = tmp_path / "output"
        _create_previous_output(final)

        staging = svc.create_staging_directory()
        (staging / "index.html").write_text("new content", encoding="utf-8")

        svc.publish(staging)

        assert (final / "index.html").read_text() == "new content"
        # Old file is gone (replaced, not merged).
        assert not (final / "marker.txt").exists()

    def test_publish_no_partial_tree(self, tmp_path: Path) -> None:
        """After publish, output contains exactly the staging content."""
        svc = OutputStagingService("output", tmp_path)
        final = tmp_path / "output"
        (final).mkdir()
        (final / "old.html").write_text("old", encoding="utf-8")

        staging = svc.create_staging_directory()
        (staging / "index.html").write_text("new", encoding="utf-8")
        (staging / "about.html").write_text("about", encoding="utf-8")

        svc.publish(staging)

        # Output has exactly the new files, not a mix.
        files = {p.name for p in final.iterdir() if p.is_file()}
        assert files == {"index.html", "about.html"}

    def test_failed_atomic_swap_preserves_both_trees(self, tmp_path: Path) -> None:
        """If the atomic swap fails, final keeps old content, staging keeps new."""
        svc = OutputStagingService("output", tmp_path)
        final = tmp_path / "output"
        _create_previous_output(final)

        staging = svc.create_staging_directory()
        (staging / "index.html").write_text("new", encoding="utf-8")

        with (
            patch(
                "github_blog.output_staging._atomic_swap",
                side_effect=OSError("Simulated swap failure"),
            ),
            pytest.raises(OutputStagingError, match="exchange failed"),
        ):
            svc.publish(staging)

        # Final has old content (unchanged by swap).
        assert (final / "index.html").read_text() == "old index"
        assert (final / "marker.txt").read_text() == "survive"
        # Staging has new content (unchanged by swap).
        assert (staging / "index.html").read_text() == "new"
        # No backup directories created (no two-step backup).
        backups = [p for p in tmp_path.iterdir() if ".backup." in p.name]
        assert not backups

    def test_publish_atomic_swap_old_tree_at_staging_path(self, tmp_path: Path) -> None:
        """After swap, the old tree is at the staging path for cleanup."""
        svc = OutputStagingService("output", tmp_path)
        final = tmp_path / "output"
        _create_previous_output(final)

        staging = svc.create_staging_directory()
        (staging / "index.html").write_text("new", encoding="utf-8")

        warnings = svc.publish(staging)

        # No warnings on clean cleanup.
        assert warnings == []
        # Final has new content.
        assert (final / "index.html").read_text() == "new"
        # Old tree (staging path) is cleaned up.
        assert not staging.exists()
        # Staging is deregistered after successful cleanup.
        assert staging.resolve() not in svc._registered_staging
        # No backup directories.
        backups = [p for p in tmp_path.iterdir() if ".backup." in p.name]
        assert not backups

    def test_publish_no_intermediate_state_on_swap_failure(
        self, tmp_path: Path
    ) -> None:
        """A failed swap must leave no rollback double-failure state.

        There is no backup to half-restore; final is either old or new,
        never missing or partial.
        """
        svc = OutputStagingService("output", tmp_path)
        final = tmp_path / "output"
        _create_previous_output(final)
        old_hash = _hash_directory(final)

        staging = svc.create_staging_directory()
        (staging / "index.html").write_text("new", encoding="utf-8")

        with (
            patch(
                "github_blog.output_staging._atomic_swap",
                side_effect=OSError("swap failed"),
            ),
            pytest.raises(OutputStagingError),
        ):
            svc.publish(staging)

        # Final is byte-for-byte unchanged (old content).
        assert _hash_directory(final) == old_hash
        # No backup dirs, no partial state.
        backups = [p for p in tmp_path.iterdir() if ".backup." in p.name]
        assert not backups

    def test_publish_post_swap_cleanup_failure_is_warning(self, tmp_path: Path) -> None:
        """If old-tree cleanup after swap fails, return a warning; final is OK."""
        svc = OutputStagingService("output", tmp_path)
        final = tmp_path / "output"
        _create_previous_output(final)

        staging = svc.create_staging_directory()
        (staging / "index.html").write_text("new", encoding="utf-8")

        with patch(
            "github_blog.output_staging.shutil.rmtree",
            side_effect=OSError("rmtree failed"),
        ):
            warnings = svc.publish(staging)

        # Final has new content (swap succeeded).
        assert (final / "index.html").read_text() == "new"
        # A warning diagnostic was returned.
        assert len(warnings) == 1
        assert warnings[0].severity == "warning"
        assert warnings[0].code == "OLD_TREE_CLEANUP_FAILED"
        # Old tree is still at staging path (rmtree failed).
        assert staging.exists()
        assert (staging / "index.html").read_text() == "old index"
        # Registration is retained so cleanup can be retried safely.
        assert staging.resolve() in svc._registered_staging
        # Registration matches the old tree now at the staging path.
        from github_blog.output_staging import _st_identity

        assert svc._registered_staging[staging.resolve()] == _st_identity(staging)

    def test_post_swap_cleanup_retry_succeeds(self, tmp_path: Path) -> None:
        """After swap, if old-tree cleanup fails, retry cleanup succeeds.

        Registration is retained on cleanup failure so that cleanup can
        be retried safely.  A retry must delete the old tree and
        deregister.
        """
        svc = OutputStagingService("output", tmp_path)
        final = tmp_path / "output"
        _create_previous_output(final)

        staging = svc.create_staging_directory()
        (staging / "index.html").write_text("new", encoding="utf-8")

        original_rmtree = shutil.rmtree
        fail_count = [0]

        def rmtree_side_effect(path: str | Path) -> None:
            if fail_count[0] == 0:
                fail_count[0] += 1
                raise OSError("rmtree failed on first attempt")
            return original_rmtree(path)

        with patch(
            "github_blog.output_staging.shutil.rmtree",
            side_effect=rmtree_side_effect,
        ):
            # Publish: swap succeeds, old-tree cleanup fails.
            warnings = svc.publish(staging)
            assert len(warnings) == 1
            assert warnings[0].code == "OLD_TREE_CLEANUP_FAILED"
            # Registration retained so cleanup can be retried.
            assert staging.resolve() in svc._registered_staging
            # Old tree still at staging path.
            assert staging.exists()
            assert (staging / "index.html").read_text() == "old index"

            # Retry cleanup: should succeed now (rmtree no longer fails).
            diags = svc.cleanup(staging)
            assert diags == []

        # Old tree deleted.
        assert not staging.exists()
        # Registration removed.
        assert staging.resolve() not in svc._registered_staging

    def test_publish_and_cleanup_reject_replaced_staging_directory(
        self, tmp_path: Path
    ) -> None:
        """A replaced staging directory (different st_dev/st_ino) is rejected.

        After moving the original and recreating at the same path, both
        publish and cleanup must reject it without mutating final/external
        data.
        """
        svc = OutputStagingService("output", tmp_path)
        final = tmp_path / "output"
        _create_previous_output(final)
        old_hash = _hash_directory(final)

        staging = svc.create_staging_directory()
        (staging / "index.html").write_text("new", encoding="utf-8")
        original_identity = _st_identity(staging)

        # Move the original staging dir away and recreate at the same path.
        moved = staging.parent / f"{staging.name}.moved"
        shutil.move(str(staging), str(moved))
        staging.mkdir(parents=True, exist_ok=False)
        (staging / "index.html").write_text("replaced", encoding="utf-8")

        # The new directory has a different (st_dev, st_ino).
        assert _st_identity(staging) != original_identity

        # Publish must reject the replaced directory.
        with pytest.raises(OutputStagingError, match="identity mismatch"):
            svc.publish(staging)
        # Final output unchanged.
        assert _hash_directory(final) == old_hash

        # Cleanup must also reject the replaced directory.
        with pytest.raises(OutputStagingError, match="identity mismatch"):
            svc.cleanup(staging)
        # The replaced dir still exists (not mutated).
        assert staging.exists()
        assert (staging / "index.html").read_text() == "replaced"
        # Final output still unchanged.
        assert _hash_directory(final) == old_hash

    def test_publish_atomic_exchange_unavailable_raises(self, tmp_path: Path) -> None:
        """If atomic exchange is unavailable, raise before changing final."""
        svc = OutputStagingService("output", tmp_path)
        final = tmp_path / "output"
        _create_previous_output(final)
        old_hash = _hash_directory(final)

        staging = svc.create_staging_directory()
        (staging / "index.html").write_text("new", encoding="utf-8")

        with (
            patch(
                "github_blog.output_staging._atomic_swap",
                side_effect=RuntimeError("not supported"),
            ),
            pytest.raises(OutputStagingError, match="unavailable"),
        ):
            svc.publish(staging)

        # Final is unchanged.
        assert _hash_directory(final) == old_hash
        # Staging is unchanged.
        assert (staging / "index.html").read_text() == "new"

    def test_cleanup_removes_staging(self, tmp_path: Path) -> None:
        svc = OutputStagingService("output", tmp_path)
        staging = svc.create_staging_directory()
        assert staging.exists()
        svc.cleanup(staging)
        assert not staging.exists()
        # Staging is deregistered after successful cleanup.
        assert staging.resolve() not in svc._registered_staging

    def test_cleanup_leaves_output_untouched(self, tmp_path: Path) -> None:
        svc = OutputStagingService("output", tmp_path)
        final = tmp_path / "output"
        _create_previous_output(final)
        staging = svc.create_staging_directory()

        svc.cleanup(staging)

        assert (final / "index.html").read_text() == "old index"
        assert (final / "marker.txt").read_text() == "survive"

    def test_cleanup_idempotent_on_registered_path(self, tmp_path: Path) -> None:
        """Cleanup on a registered-but-removed path is a no-op."""
        svc = OutputStagingService("output", tmp_path)
        staging = svc.create_staging_directory()
        svc.cleanup(staging)
        assert not staging.exists()
        # Second cleanup is idempotent (registered, already gone).
        diags = svc.cleanup(staging)
        assert diags == []

    def test_cleanup_rejects_unregistered_path(self, tmp_path: Path) -> None:
        """Cleanup on an unregistered, existing path must raise."""
        svc = OutputStagingService("output", tmp_path)
        fake = tmp_path / "unregistered_dir"
        fake.mkdir()
        with pytest.raises(OutputStagingError, match="unregistered"):
            svc.cleanup(fake)

    def test_publish_rejects_unregistered_path(self, tmp_path: Path) -> None:
        """Publish on an unregistered path must raise."""
        svc = OutputStagingService("output", tmp_path)
        fake_staging = tmp_path / "fake_staging"
        fake_staging.mkdir()
        (fake_staging / "index.html").write_text("x", encoding="utf-8")
        with pytest.raises(OutputStagingError, match="unregistered"):
            svc.publish(fake_staging)

    def test_publish_rejects_external_path(self, tmp_path: Path) -> None:
        """Publish on a path outside staging parent must raise."""
        import shutil

        svc = OutputStagingService("output", tmp_path)
        # Create a staging dir legitimately, then try to publish an
        # external path.
        external = tmp_path.parent / "external_staging_dir"
        if external.exists():
            shutil.rmtree(external)
        external.mkdir(exist_ok=True)
        (external / "index.html").write_text("x", encoding="utf-8")
        try:
            with pytest.raises(OutputStagingError, match="unregistered"):
                svc.publish(external)
        finally:
            shutil.rmtree(external, ignore_errors=True)

    def test_publish_rejects_symlinked_path(self, tmp_path: Path) -> None:
        """Publish on a symlinked staging path must raise."""
        import os

        svc = OutputStagingService("output", tmp_path)
        staging = svc.create_staging_directory()
        (staging / "index.html").write_text("new", encoding="utf-8")

        # Create a symlink to the staging dir.
        link = tmp_path / ".output.staging.symlink"
        os.symlink(staging, link)

        with pytest.raises(OutputStagingError, match="symlink"):
            svc.publish(link)

    def test_cleanup_surfaces_error_on_failure(self, tmp_path: Path) -> None:
        """Cleanup failure must return an error diagnostic, not silently ignore."""
        svc = OutputStagingService("output", tmp_path)
        staging = svc.create_staging_directory()
        (staging / "index.html").write_text("new", encoding="utf-8")

        with patch(
            "github_blog.output_staging.shutil.rmtree",
            side_effect=OSError("rmtree permission denied"),
        ):
            diags = svc.cleanup(staging)

        assert len(diags) == 1
        assert diags[0].severity == "error"
        assert diags[0].code == "CLEANUP_FAILED"
        # Staging dir still exists (rmtree failed).
        assert staging.exists()

    def test_unsafe_output_rejected_in_constructor(self, tmp_path: Path) -> None:
        with pytest.raises(OutputContainmentError):
            OutputStagingService("src", tmp_path)


# ---------------------------------------------------------------------------
# BlogGenerator staging integration
# ---------------------------------------------------------------------------


class TestBlogGeneratorStaging:
    def test_successful_build_returns_success_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from github_blog.cli import BlogGenerator

        monkeypatch.chdir(tmp_path)
        _setup_minimal_theme(tmp_path)
        settings = _make_settings(tmp_path)

        issues = [_make_mock_issue(1, "Test Post", labels=["python"])]
        gh = _make_fake_github_service(issues=issues)
        render = _make_fake_render_service()

        gen = BlogGenerator(
            "fake-token",
            "user/repo",
            settings,
            github_service=gh,
            render_service=render,
        )
        result = gen.generate()

        assert result.success
        assert result.diagnostics == ()

    def test_successful_build_replaces_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from github_blog.cli import BlogGenerator

        monkeypatch.chdir(tmp_path)
        _setup_minimal_theme(tmp_path)
        settings = _make_settings(tmp_path)

        # Create previous output.
        final = tmp_path / "output"
        _create_previous_output(final)

        issues = [_make_mock_issue(1, "Test Post", labels=["python"])]
        gh = _make_fake_github_service(issues=issues)
        render = _make_fake_render_service()

        gen = BlogGenerator(
            "fake-token",
            "user/repo",
            settings,
            github_service=gh,
            render_service=render,
        )
        result = gen.generate()

        assert result.success
        # Old marker is gone; new content is present.
        assert not (final / "marker.txt").exists()
        assert (final / "index.html").exists()
        assert (final / "blog").exists()

    def test_no_staging_dir_left_on_success(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from github_blog.cli import BlogGenerator

        monkeypatch.chdir(tmp_path)
        _setup_minimal_theme(tmp_path)
        settings = _make_settings(tmp_path)

        issues = [_make_mock_issue(1, "Test Post")]
        gh = _make_fake_github_service(issues=issues)
        render = _make_fake_render_service()

        gen = BlogGenerator(
            "fake-token",
            "user/repo",
            settings,
            github_service=gh,
            render_service=render,
        )
        gen.generate()

        _assert_no_staging_dirs(tmp_path)

    def test_fetch_failure_preserves_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from github_blog.cli import BlogGenerator

        monkeypatch.chdir(tmp_path)
        settings = _make_settings(tmp_path)

        final = tmp_path / "output"
        _create_previous_output(final)
        old_hash = _hash_directory(final)

        gh = _make_failing_github_service()
        render = _make_fake_render_service()

        gen = BlogGenerator(
            "fake-token",
            "user/repo",
            settings,
            github_service=gh,
            render_service=render,
        )
        result = gen.generate()

        assert not result.success
        assert any(d.code == "FETCH_FAILED" for d in result.diagnostics)
        # Previous output byte-for-byte unchanged.
        assert _hash_directory(final) == old_hash
        _assert_no_staging_dirs(tmp_path)

    def test_render_failure_preserves_output_byte_for_byte(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from github_blog.cli import BlogGenerator

        monkeypatch.chdir(tmp_path)
        _setup_minimal_theme(tmp_path)
        settings = _make_settings(tmp_path)

        final = tmp_path / "output"
        _create_previous_output(final)
        old_hash = _hash_directory(final)

        issues = [_make_mock_issue(1, "Test Post")]
        gh = _make_fake_github_service(issues=issues)
        render = _make_failing_render_service()

        gen = BlogGenerator(
            "fake-token",
            "user/repo",
            settings,
            github_service=gh,
            render_service=render,
        )
        result = gen.generate()

        assert not result.success
        assert any(d.code == "RENDER_FAILED" for d in result.diagnostics)
        # The RENDER_FAILED diagnostic carries the issue number.
        render_diag = next(d for d in result.diagnostics if d.code == "RENDER_FAILED")
        assert render_diag.issue_number == 1
        # The Markdown collaborator was invoked before the render failure.
        render.markdown_to_html.assert_called()
        # The template-render collaborator was actually invoked.
        render.render_post.assert_called()
        # Previous output byte-for-byte unchanged.
        assert _hash_directory(final) == old_hash
        _assert_no_staging_dirs(tmp_path)

    def test_first_publication_rename_failure_returns_publish_failed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A first-publication rename failure must return PUBLISH_FAILED."""
        from github_blog.cli import BlogGenerator
        from github_blog.output_staging import OutputStagingService

        monkeypatch.chdir(tmp_path)
        _setup_minimal_theme(tmp_path)
        settings = _make_settings(tmp_path)

        # No previous output -- first publication path.
        issues = [_make_mock_issue(1, "Test Post")]
        gh = _make_fake_github_service(issues=issues)
        render = _make_fake_render_service()

        # Inject a staging service whose publish raises OSError on rename.
        staging = MagicMock(spec=OutputStagingService)
        staging.create_staging_directory.side_effect = lambda: (
            _create_staging_and_return(tmp_path)
        )
        staging.publish.side_effect = OSError("cross-device rename")
        staging.cleanup.return_value = []

        gen = BlogGenerator(
            "fake-token",
            "user/repo",
            settings,
            github_service=gh,
            render_service=render,
            output_staging=staging,
        )
        result = gen.generate()

        assert not result.success
        assert any(d.code == "PUBLISH_FAILED" for d in result.diagnostics)

    def test_validation_failure_preserves_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from github_blog.cli import BlogGenerator

        monkeypatch.chdir(tmp_path)
        _setup_minimal_theme(tmp_path)
        settings = _make_settings(tmp_path)

        final = tmp_path / "output"
        _create_previous_output(final)
        old_hash = _hash_directory(final)

        issues = [_make_mock_issue(1, "Test Post")]
        gh = _make_fake_github_service(issues=issues)
        render = _make_fake_render_service()

        failing_validator = MagicMock()
        failing_validator.validate.return_value = [
            Diagnostic(
                severity="error",
                code="VALIDATION_FAILED",
                message="validation failed for testing",
            )
        ]

        gen = BlogGenerator(
            "fake-token",
            "user/repo",
            settings,
            github_service=gh,
            render_service=render,
            artifact_validator=failing_validator,
        )
        result = gen.generate()

        assert not result.success
        assert any(d.code == "VALIDATION_FAILED" for d in result.diagnostics)
        # Previous output byte-for-byte unchanged.
        assert _hash_directory(final) == old_hash
        _assert_no_staging_dirs(tmp_path)

    def test_containment_failure_preserves_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unsafe output path must fail before any filesystem mutation."""
        from github_blog.cli import BlogGenerator

        monkeypatch.chdir(tmp_path)
        # Use a protected root as output.
        settings = _make_settings(tmp_path, output="src")

        # Create "src" with a file that must survive.
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "important.py").write_text("# important", encoding="utf-8")

        issues = [_make_mock_issue(1, "Test Post")]
        gh = _make_fake_github_service(issues=issues)
        render = _make_fake_render_service()

        gen = BlogGenerator(
            "fake-token",
            "user/repo",
            settings,
            github_service=gh,
            render_service=render,
        )
        result = gen.generate()

        assert not result.success
        assert any(d.code == "OUTPUT_CONTAINMENT_FAILED" for d in result.diagnostics)
        assert (src_dir / "important.py").read_text() == "# important"

    def test_generate_does_not_call_sys_exit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Core build code must never call sys.exit directly."""
        from github_blog.cli import BlogGenerator

        monkeypatch.chdir(tmp_path)
        settings = _make_settings(tmp_path)

        gh = _make_failing_github_service()
        render = _make_fake_render_service()

        gen = BlogGenerator(
            "fake-token",
            "user/repo",
            settings,
            github_service=gh,
            render_service=render,
        )
        # Must return a BuildResult, not raise SystemExit.
        result = gen.generate()
        assert isinstance(result, BuildResult)
        assert not result.success

    def test_slug_preparation_failure_preserves_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failure during slug preparation must return a structured diagnostic.

        Slug/content preparation runs before any filesystem mutation, so
        previous output is preserved byte-for-byte.
        """
        from github_blog.cli import BlogGenerator

        monkeypatch.chdir(tmp_path)
        settings = _make_settings(tmp_path)

        final = tmp_path / "output"
        _create_previous_output(final)
        old_hash = _hash_directory(final)

        issues = [_make_mock_issue(1, "Test Post")]
        gh = _make_fake_github_service(issues=issues)
        render = _make_fake_render_service()

        gen = BlogGenerator(
            "fake-token",
            "user/repo",
            settings,
            github_service=gh,
            render_service=render,
        )
        with patch(
            "github_blog.cli.generate_slug_from_title",
            side_effect=RuntimeError("slug explosion"),
        ):
            result = gen.generate()

        assert not result.success
        assert any(d.code == "SLUG_PREPARATION_FAILED" for d in result.diagnostics)
        # No staging dirs created.
        _assert_no_staging_dirs(tmp_path)
        # Previous output byte-for-byte unchanged.
        assert _hash_directory(final) == old_hash

    def test_markdown_parse_failure_preserves_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A parse failure during content rendering must preserve output."""
        from github_blog.cli import BlogGenerator

        monkeypatch.chdir(tmp_path)
        _setup_minimal_theme(tmp_path)
        settings = _make_settings(tmp_path)

        final = tmp_path / "output"
        _create_previous_output(final)
        old_hash = _hash_directory(final)

        issues = [_make_mock_issue(1, "Test Post")]
        gh = _make_fake_github_service(issues=issues)
        render = _make_fake_render_service()
        render.markdown_to_html.side_effect = RuntimeError("markdown parse failed")

        gen = BlogGenerator(
            "fake-token",
            "user/repo",
            settings,
            github_service=gh,
            render_service=render,
        )
        result = gen.generate()

        assert not result.success
        assert any(d.code == "MARKDOWN_CONVERT_FAILED" for d in result.diagnostics)
        # The MARKDOWN_CONVERT_FAILED diagnostic carries the issue number.
        convert_diag = next(
            d for d in result.diagnostics if d.code == "MARKDOWN_CONVERT_FAILED"
        )
        assert convert_diag.issue_number == 1
        # The Markdown collaborator was actually invoked.
        render.markdown_to_html.assert_called()
        # The template-render collaborator was NOT invoked (Markdown failed first).
        render.render_post.assert_not_called()
        # Previous output byte-for-byte unchanged.
        assert _hash_directory(final) == old_hash
        _assert_no_staging_dirs(tmp_path)

    def test_staging_creation_failure_returns_staging_creation_failed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A staging-directory creation failure must report STAGING_CREATION_FAILED.

        Uses an injected OutputStagingService whose
        ``create_staging_directory`` raises, then asserts the exact stage
        code and that the intended collaborator was called.
        """
        from github_blog.cli import BlogGenerator
        from github_blog.output_staging import OutputStagingService

        monkeypatch.chdir(tmp_path)
        settings = _make_settings(tmp_path)

        final = tmp_path / "output"
        _create_previous_output(final)
        old_hash = _hash_directory(final)

        issues = [_make_mock_issue(1, "Test Post")]
        gh = _make_fake_github_service(issues=issues)
        render = _make_fake_render_service()

        staging = MagicMock(spec=OutputStagingService)
        staging.create_staging_directory.side_effect = OSError(
            "cannot create staging dir"
        )
        staging.cleanup.return_value = []

        gen = BlogGenerator(
            "fake-token",
            "user/repo",
            settings,
            github_service=gh,
            render_service=render,
            output_staging=staging,
        )
        result = gen.generate()

        assert not result.success
        assert any(d.code == "STAGING_CREATION_FAILED" for d in result.diagnostics)
        # The staging collaborator was actually invoked.
        staging.create_staging_directory.assert_called_once()
        # No rendering happened (staging was never created).
        render.markdown_to_html.assert_not_called()
        # Previous output byte-for-byte unchanged.
        assert _hash_directory(final) == old_hash

    def test_build_setup_failure_returns_build_setup_failed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A render/output setup failure must report BUILD_SETUP_FAILED.

        The theme directory is deliberately absent so ``_copy_theme_assets``
        raises; the test asserts the exact stage code and that rendering
        never started.
        """
        from github_blog.cli import BlogGenerator

        monkeypatch.chdir(tmp_path)
        # Deliberately do NOT call _setup_minimal_theme so _copy_theme_assets
        # fails with FileNotFoundError.
        settings = _make_settings(tmp_path)

        final = tmp_path / "output"
        _create_previous_output(final)
        old_hash = _hash_directory(final)

        issues = [_make_mock_issue(1, "Test Post")]
        gh = _make_fake_github_service(issues=issues)
        render = _make_fake_render_service()

        gen = BlogGenerator(
            "fake-token",
            "user/repo",
            settings,
            github_service=gh,
            render_service=render,
        )
        result = gen.generate()

        assert not result.success
        assert any(d.code == "BUILD_SETUP_FAILED" for d in result.diagnostics)
        # No rendering happened (setup failed before render phase).
        render.markdown_to_html.assert_not_called()
        # Previous output byte-for-byte unchanged.
        assert _hash_directory(final) == old_hash
        _assert_no_staging_dirs(tmp_path)

    def test_validation_warnings_do_not_block_publication(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Artifact validation warnings must not block publication."""
        from github_blog.cli import BlogGenerator

        monkeypatch.chdir(tmp_path)
        _setup_minimal_theme(tmp_path)
        settings = _make_settings(tmp_path)

        final = tmp_path / "output"
        _create_previous_output(final)

        issues = [_make_mock_issue(1, "Test Post")]
        gh = _make_fake_github_service(issues=issues)
        render = _make_fake_render_service()

        warning_validator = MagicMock()
        warning_validator.validate.return_value = [
            Diagnostic(
                severity="warning",
                code="MINOR_WARNING",
                message="a non-blocking warning",
            )
        ]

        gen = BlogGenerator(
            "fake-token",
            "user/repo",
            settings,
            github_service=gh,
            render_service=render,
            artifact_validator=warning_validator,
        )
        result = gen.generate()

        assert result.success
        # Warning is preserved in the result.
        assert any(
            d.severity == "warning" and d.code == "MINOR_WARNING"
            for d in result.diagnostics
        )
        # New content was published (old marker gone).
        assert not (final / "marker.txt").exists()
        assert (final / "index.html").exists()

    def test_warnings_preserved_in_successful_build_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A successful build with warnings must retain them in diagnostics."""
        from github_blog.cli import BlogGenerator

        monkeypatch.chdir(tmp_path)
        _setup_minimal_theme(tmp_path)
        settings = _make_settings(tmp_path)

        issues = [_make_mock_issue(1, "Test Post")]
        gh = _make_fake_github_service(issues=issues)
        render = _make_fake_render_service()

        warning_validator = MagicMock()
        warning_validator.validate.return_value = [
            Diagnostic(
                severity="warning",
                code="CHECK_STYLE",
                message="style suggestion",
            ),
            Diagnostic(
                severity="warning",
                code="ACCESSIBILITY",
                message="alt text missing",
            ),
        ]

        gen = BlogGenerator(
            "fake-token",
            "user/repo",
            settings,
            github_service=gh,
            render_service=render,
            artifact_validator=warning_validator,
        )
        result = gen.generate()

        assert result.success
        warning_codes = [d.code for d in result.diagnostics if d.severity == "warning"]
        assert "CHECK_STYLE" in warning_codes
        assert "ACCESSIBILITY" in warning_codes
        # No errors.
        assert not any(d.severity == "error" for d in result.diagnostics)

    def test_artifact_validator_exception_preserves_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An artifact validator that raises must return ARTIFACT_VALIDATION_FAILED."""
        from github_blog.cli import BlogGenerator

        monkeypatch.chdir(tmp_path)
        _setup_minimal_theme(tmp_path)
        settings = _make_settings(tmp_path)

        final = tmp_path / "output"
        _create_previous_output(final)
        old_hash = _hash_directory(final)

        issues = [_make_mock_issue(1, "Test Post")]
        gh = _make_fake_github_service(issues=issues)
        render = _make_fake_render_service()

        exception_validator = MagicMock()
        exception_validator.validate.side_effect = RuntimeError("validator crashed")

        gen = BlogGenerator(
            "fake-token",
            "user/repo",
            settings,
            github_service=gh,
            render_service=render,
            artifact_validator=exception_validator,
        )
        result = gen.generate()

        assert not result.success
        assert any(d.code == "ARTIFACT_VALIDATION_FAILED" for d in result.diagnostics)
        # The validator was actually invoked.
        exception_validator.validate.assert_called_once()
        # Previous output byte-for-byte unchanged.
        assert _hash_directory(final) == old_hash
        _assert_no_staging_dirs(tmp_path)


# ---------------------------------------------------------------------------
# run_cli maps BuildResult to exit status
# ---------------------------------------------------------------------------


class TestRunCliBuildResult:
    def _setup_config(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("G_T", "fake-token")
        monkeypatch.setattr(sys, "argv", ["blog-gen"])
        monkeypatch.chdir(tmp_path)
        config = """
github:
  repo: user/repo
  allowed_authors:
    - user
site:
  title: Test Blog
  url: https://example.com/
  author: Test
about:
  issue_number: 1
security:
  token_env: G_T
"""
        (tmp_path / "config.yaml").write_text(config)

    def test_run_cli_exits_on_build_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._setup_config(tmp_path, monkeypatch)

        with patch("github_blog.cli.BlogGenerator") as mock_gen_class:
            mock_gen = MagicMock()
            mock_gen.generate.return_value = BuildResult(
                success=False,
                diagnostics=(
                    Diagnostic(
                        severity="error",
                        code="TEST_FAILURE",
                        message="test failure",
                    ),
                ),
            )
            mock_gen_class.return_value = mock_gen

            with pytest.raises(SystemExit) as exc_info:
                from github_blog.cli import run_cli

                run_cli()
            assert exc_info.value.code == 1

    def test_run_cli_does_not_exit_on_success(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._setup_config(tmp_path, monkeypatch)

        with patch("github_blog.cli.BlogGenerator") as mock_gen_class:
            mock_gen = MagicMock()
            mock_gen.generate.return_value = BuildResult(success=True)
            mock_gen_class.return_value = mock_gen

            from github_blog.cli import run_cli

            run_cli()  # Must not raise SystemExit.
            mock_gen.generate.assert_called_once()

    def test_run_cli_logs_warnings_on_success(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """run_cli must log warnings even when the build succeeds."""
        self._setup_config(tmp_path, monkeypatch)

        with patch("github_blog.cli.BlogGenerator") as mock_gen_class:
            mock_gen = MagicMock()
            mock_gen.generate.return_value = BuildResult(
                success=True,
                diagnostics=(
                    Diagnostic(
                        severity="warning",
                        code="MINOR_WARNING",
                        message="non-blocking warning",
                        issue_number=42,
                        field="slug",
                    ),
                ),
            )
            mock_gen_class.return_value = mock_gen

            with patch("github_blog.cli.logger") as mock_logger:
                from github_blog.cli import run_cli

                run_cli()  # Must not raise SystemExit.

            mock_gen.generate.assert_called_once()
            # Warning was logged with structured fields including
            # issue_number and field when present.
            mock_logger.warning.assert_called_once_with(
                "build_diagnostic",
                code="MINOR_WARNING",
                message="non-blocking warning",
                issue_number=42,
                field="slug",
            )

    def test_run_cli_logs_warnings_on_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """run_cli must log warnings even when the build fails."""
        self._setup_config(tmp_path, monkeypatch)

        with patch("github_blog.cli.BlogGenerator") as mock_gen_class:
            mock_gen = MagicMock()
            mock_gen.generate.return_value = BuildResult(
                success=False,
                diagnostics=(
                    Diagnostic(
                        severity="error",
                        code="BUILD_FAILED",
                        message="boom",
                    ),
                    Diagnostic(
                        severity="warning",
                        code="MINOR_WARNING",
                        message="non-blocking warning",
                    ),
                ),
            )
            mock_gen_class.return_value = mock_gen

            with (
                patch("github_blog.cli.logger") as mock_logger,
                pytest.raises(SystemExit) as exc_info,
            ):
                from github_blog.cli import run_cli

                run_cli()
            assert exc_info.value.code == 1
            # Error was logged with structured fields.
            mock_logger.error.assert_called_once_with(
                "build_diagnostic",
                code="BUILD_FAILED",
                message="boom",
            )
            # Warning was also logged.
            mock_logger.warning.assert_called_once_with(
                "build_diagnostic",
                code="MINOR_WARNING",
                message="non-blocking warning",
            )
