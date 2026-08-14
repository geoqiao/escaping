"""Output staging and portable publication.

Keeps a fully rendered and validated candidate tree under the validated
output boundary/parent, then replaces final output with directory renames
without exposing a partially copied tree.

When final output already exists, it is renamed to a uniquely owned sibling
backup before the candidate is renamed into place.  If candidate promotion
fails, the backup is restored.  Successful local publication may therefore
have a brief window in which the final path is absent, but it never copies a
candidate into final file by file.

When final does not exist, a single ``os.rename`` suffices.

After successful publication the backup is cleaned up; cleanup failure
produces a warning diagnostic and never invalidates the new final.  If
rollback itself fails, candidate and backup recovery material is preserved
and the raised error reports all recovery paths.

Failures before publication clean up candidate output and preserve the
previous final output byte-for-byte.  The staging directory is created as a
sibling of the final output, within the containment boundary validated by
:func:`escaping.output_safety.validate_output_containment`.

The service owns and tracks every staging directory and backup path it
creates.  At mutation boundaries it rejects arbitrary, external, moved,
symlinked, wrong-parent, or unregistered paths.

Concurrent local builds targeting the same output directory are unsupported.
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

import structlog

from .build_result import Diagnostic
from .output_safety import OutputContainmentError, validate_output_containment

logger = structlog.get_logger()


# --- Staging identity ------------------------------------------------------


def _st_identity(path: Path) -> tuple[int, int]:
    """Return ``(st_dev, st_ino)`` for owned-tree identity tracking.

    Using both device and inode avoids false matches across different
    filesystems, which ``st_ino`` alone cannot distinguish.
    """
    st = path.stat()
    return (st.st_dev, st.st_ino)


class OutputStagingError(Exception):
    """Raised when a staging operation violates containment or registration.

    ``recovery_paths`` is non-empty only when automatic rollback failed and
    the caller must preserve those paths for manual recovery.
    """

    def __init__(
        self,
        message: str,
        *,
        recovery_paths: tuple[Path, ...] = (),
    ) -> None:
        super().__init__(message)
        self.recovery_paths = recovery_paths


class OutputStagingService:
    """Manages candidate output staging and portable publication.

    The staging directory is created as a sibling of the final output,
    within the validated containment boundary.  The service tracks every
    staging directory it creates and rejects unregistered, external,
    moved, symlinked, or wrong-parent paths at ``publish`` and
    ``cleanup`` mutation boundaries.
    """

    def __init__(self, output_path: str | Path, repo_root: Path) -> None:
        self._output = validate_output_containment(output_path, repo_root)
        self._repo_root = repo_root.resolve()
        self._staging_parent = self._output.parent
        # Maps resolved staging path -> (st_dev, st_ino) at creation time.
        self._registered_staging: dict[Path, tuple[int, int]] = {}
        # Backup paths are reserved with the final tree's identity before rename.
        self._registered_backups: dict[Path, tuple[int, int]] = {}

    # --- Staging creation ------------------------------------------------

    def create_staging_directory(self) -> Path:
        """Create a temporary staging directory as a sibling of the output.

        The directory name uses a unique suffix to avoid collisions.
        Returns the path to the created directory.  The service tracks
        this path so that ``publish`` and ``cleanup`` can verify it later.
        """
        suffix = uuid.uuid4().hex[:12]
        staging_name = f".{self._output.name}.staging.{suffix}"
        staging_dir = self._staging_parent / staging_name

        self._validate_owned_sibling(staging_dir, "staging")

        staging_dir.mkdir(parents=True, exist_ok=False)
        resolved = staging_dir.resolve()
        self._registered_staging[resolved] = _st_identity(staging_dir)
        return staging_dir

    # --- Registration verification ---------------------------------------

    # TOCTOU boundary: _verify_owned reads the filesystem identity at
    # check time, but between this check and the subsequent mutation
    # (rmtree / rename) the path could be replaced by another process
    # on the same machine.  This is a local-concurrency TOCTOU race that
    # cannot be eliminated without fd-based operations (e.g. openat with
    # O_NOFOLLOW).  The current implementation does not attempt fd-based
    # hardening; the identity check reduces the attack surface but does not
    # provide a guarantee.

    def _validate_owned_sibling(self, path: Path, kind: str) -> Path:
        """Validate a generated staging/backup path before it is owned."""
        if path.is_symlink():
            raise OutputContainmentError(
                f"{kind} directory must not be a symlink: {path}"
            )
        resolved = path.resolve()
        expected_parent = self._staging_parent.resolve()
        if resolved.parent != expected_parent:
            raise OutputContainmentError(
                f"{kind} directory must be a sibling of final output: {path}"
            )
        try:
            resolved.relative_to(self._repo_root)
        except ValueError as exc:
            raise OutputContainmentError(
                f"{kind} directory escapes repo root: {path}"
            ) from exc
        return resolved

    def _verify_owned(
        self,
        path: Path,
        registry: dict[Path, tuple[int, int]],
        kind: str,
    ) -> None:
        """Verify a registered staging/backup path is still safe to mutate."""
        label = f"{kind} directory"
        if path.is_symlink():
            raise OutputStagingError(
                f"{label} is a symlink (refusing to mutate): {path}"
            )

        resolved = path.resolve()
        if resolved not in registry:
            raise OutputStagingError(
                f"{label} was not created by this service (unregistered): {path}"
            )

        expected_parent = self._staging_parent.resolve()
        if resolved.parent != expected_parent:
            raise OutputStagingError(
                f"{label} has wrong parent (moved or external): {path} "
                f"(expected {expected_parent}, got {resolved.parent})"
            )

        if path.exists():
            expected_identity = registry[resolved]
            try:
                actual_identity = _st_identity(path)
            except OSError as exc:
                raise OutputStagingError(
                    f"{label} disappeared or became unreadable during verification: "
                    f"{path} ({exc})"
                ) from exc
            if expected_identity != actual_identity:
                raise OutputStagingError(
                    f"{label} identity mismatch (path was replaced or moved): {path}"
                )

    def _verify_registered(self, staging_dir: Path) -> None:
        """Verify *staging_dir* was created by this service and is safe.

        Rejects symlinks, unregistered paths, wrong-parent paths, and
        paths whose ``(st_dev, st_ino)`` differs from creation time
        (moved or replaced).

        Raises:
            OutputStagingError: If any safety check fails.
        """
        self._verify_owned(staging_dir, self._registered_staging, "staging")

    def _verify_registered_backup(self, backup_dir: Path) -> None:
        """Verify a backup was reserved by this service and is unchanged."""
        self._verify_owned(backup_dir, self._registered_backups, "backup")

    def _deregister(self, staging_dir: Path) -> None:
        """Remove a staging path from the registration set."""
        self._registered_staging.pop(staging_dir.resolve(), None)

    def _reserve_backup_path(self) -> Path:
        """Reserve a unique sibling path with the current final tree identity."""
        suffix = uuid.uuid4().hex[:12]
        backup_dir = self._staging_parent / f".{self._output.name}.backup.{suffix}"
        resolved = self._validate_owned_sibling(backup_dir, "backup")
        if backup_dir.exists() or backup_dir.is_symlink():
            raise OutputStagingError(f"backup path already exists: {backup_dir}")
        try:
            self._registered_backups[resolved] = _st_identity(self._output)
        except OSError as exc:
            raise OutputStagingError(
                "final output disappeared before backup reservation; concurrent "
                "local builds to the same output are unsupported: "
                f"final={self._output} ({exc})"
            ) from exc
        return backup_dir

    def _deregister_backup(self, backup_dir: Path) -> None:
        """Remove a backup path from the registration set."""
        self._registered_backups.pop(backup_dir.resolve(), None)

    # --- Publication -----------------------------------------------------

    def publish(self, staging_dir: Path) -> list[Diagnostic]:
        """Publish a validated staging directory with portable renames.

        When final output already exists, it is renamed to a registered
        sibling backup before staging is renamed into place.  Failure to
        promote staging restores the backup.  When final does not exist, a
        single ``os.rename`` is used.

        After successful promotion, backup cleanup is best effort: failure
        produces a warning and leaves the complete new output published.
        If rollback fails, this method raises an error with ``recovery_paths``
        so callers preserve candidate and backup trees for manual recovery.

        Returns:
            A list of warning :class:`Diagnostic` instances (e.g. from
            backup cleanup).  Empty on a clean success.

        Raises:
            FileNotFoundError: If *staging_dir* does not exist.
            OutputStagingError: If the path is unregistered, external,
                moved, symlinked, or wrong-parent, or publication/rollback
                fails.
        """
        self._verify_registered(staging_dir)

        if not staging_dir.exists():
            raise FileNotFoundError(f"Staging directory not found: {staging_dir}")

        if not self._output.exists():
            # Final does not exist -- a single directory rename is sufficient.
            os.rename(staging_dir, self._output)
            self._deregister(staging_dir)
            return []

        backup_dir = self._reserve_backup_path()
        try:
            os.rename(self._output, backup_dir)
        except OSError as exc:
            self._deregister_backup(backup_dir)
            raise OutputStagingError(
                "Failed to move existing output to backup; final output unchanged: "
                f"final={self._output}; backup={backup_dir}; error={exc}"
            ) from exc

        try:
            os.rename(staging_dir, self._output)
        except OSError as promotion_error:
            try:
                self._verify_registered_backup(backup_dir)
                os.rename(backup_dir, self._output)
            except (OSError, OutputStagingError) as rollback_error:
                recovery_paths = tuple(
                    path
                    for path in (staging_dir, backup_dir, self._output)
                    if path.exists() or path.is_symlink()
                )
                raise OutputStagingError(
                    "Candidate promotion failed and rollback failed; recovery "
                    "material was preserved. "
                    f"final={self._output}; candidate={staging_dir}; "
                    f"backup={backup_dir}; promotion_error={promotion_error}; "
                    f"rollback_error={rollback_error}",
                    recovery_paths=recovery_paths,
                ) from rollback_error
            self._deregister_backup(backup_dir)
            raise OutputStagingError(
                "Candidate promotion failed; restored previous output. "
                f"final={self._output}; candidate={staging_dir}; "
                f"promotion_error={promotion_error}"
            ) from promotion_error

        self._deregister(staging_dir)

        # Best-effort cleanup of the old output tree at the backup path.
        warnings: list[Diagnostic] = []
        try:
            if backup_dir.exists() or backup_dir.is_symlink():
                self._verify_registered_backup(backup_dir)
                shutil.rmtree(backup_dir)
            self._deregister_backup(backup_dir)
        except (OSError, OutputStagingError) as exc:
            logger.warning(
                "backup_cleanup_failed",
                path=str(backup_dir),
                error=str(exc),
            )
            warnings.append(
                Diagnostic(
                    severity="warning",
                    code="BACKUP_CLEANUP_FAILED",
                    message=(
                        "Published new output, but failed to clean up the "
                        f"previous output backup: {backup_dir} ({exc})"
                    ),
                )
            )
        return warnings

    # --- Cleanup ---------------------------------------------------------

    def cleanup(self, staging_dir: Path) -> list[Diagnostic]:
        """Remove a staging directory on failure.

        Verifies that *staging_dir* was created by this service and is
        safe to remove before attempting deletion.

        Cleanup failures are surfaced as structured error diagnostics
        rather than silently ignored.  The method does **not** raise on
        ``shutil.rmtree`` failure -- it returns the diagnostic so the
        caller can include it in the :class:`BuildResult`.

        Deregisters after successful cleanup or confirmed absence.
        Idempotent for paths already deregistered and gone: returns an
        empty list.

        Returns:
            A list of error :class:`Diagnostic` instances for cleanup
            failures.  Empty on success or when the path no longer exists.

        Raises:
            OutputStagingError: If the path exists but is unregistered,
                external, moved, symlinked, or wrong-parent (programming
                error).
        """
        resolved = staging_dir.resolve()

        # Idempotent: if the path was already cleaned up (deregistered
        # and gone), there is nothing to do.
        if resolved not in self._registered_staging:
            if not staging_dir.exists():
                return []
            raise OutputStagingError(
                f"staging directory was not created by this service "
                f"(unregistered): {staging_dir}"
            )

        self._verify_registered(staging_dir)

        if not staging_dir.exists():
            # Confirmed absence: deregister and return.
            self._deregister(staging_dir)
            return []

        diagnostics: list[Diagnostic] = []
        try:
            shutil.rmtree(staging_dir)
            self._deregister(staging_dir)
        except OSError as exc:
            logger.error("cleanup_failed", path=str(staging_dir), error=str(exc))
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="CLEANUP_FAILED",
                    message=(
                        f"Failed to clean up staging directory: {staging_dir} ({exc})"
                    ),
                )
            )
        return diagnostics
