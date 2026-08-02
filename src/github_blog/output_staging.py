"""Output staging and atomic publication.

Keeps a fully rendered and validated candidate tree under the validated
output boundary/parent, then replaces final output atomically without
exposing a partially copied tree.

When final output already exists, a true atomic directory exchange
(platform-specific POSIX primitive: ``renamex_np`` on macOS,
``renameat2`` on Linux) swaps the staging and final paths so that final
never disappears.  If the platform lacks an atomic-exchange primitive,
publication fails *before* changing final -- no non-atomic backup/restore
fallback is attempted.

When final does not exist, a single ``os.rename`` suffices.

After a successful exchange the old tree (now at the former staging path)
is cleaned up; cleanup failure produces a warning diagnostic and never
corrupts the new final.

Failed builds clean up candidate output and preserve the previous final
output byte-for-byte.  The staging directory is created as a sibling of
the final output, within the containment boundary validated by
:func:`github_blog.output_safety.validate_output_containment`.

The service owns and tracks every staging directory it creates.  At
``publish`` and ``cleanup`` mutation boundaries it rejects arbitrary,
external, moved, symlinked, wrong-parent, or unregistered paths.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import shutil
import sys
import uuid
from pathlib import Path

import structlog

from .build_result import Diagnostic
from .output_safety import OutputContainmentError, validate_output_containment

logger = structlog.get_logger()


# --- Staging identity ------------------------------------------------------


def _st_identity(path: Path) -> tuple[int, int]:
    """Return ``(st_dev, st_ino)`` for staging-identity tracking.

    Using both device and inode avoids false matches across different
    filesystems, which ``st_ino`` alone cannot distinguish.
    """
    st = path.stat()
    return (st.st_dev, st.st_ino)


# --- Atomic exchange primitives ---------------------------------------------

# RENAME_SWAP (macOS) and RENAME_EXCHANGE (Linux) both have the value 2.
# macOS: <sys/stdio.h>  #define RENAME_SWAP  0x00000002
# Linux: <linux/fs.h>    #define RENAME_EXCHANGE  (1 << 1) == 2
_RENAME_SWAP_FLAG: int = 2

# Linux AT_FDCWD for renameat2.
_AT_FDCWD: int = -100


def _atomic_swap(path_a: str, path_b: str) -> None:
    """Atomically swap two filesystem paths.

    Uses ``renamex_np`` (macOS) or ``renameat2`` (Linux) with the
    exchange/swap flag so that both paths are atomically exchanged.

    Raises:
        RuntimeError: If the platform does not support an atomic swap
            primitive.
        OSError: If the swap operation fails at the syscall level.
    """
    if sys.platform == "darwin":
        _swap_macos(path_a, path_b)
    elif sys.platform.startswith("linux"):
        _swap_linux(path_a, path_b)
    else:
        raise RuntimeError(f"atomic directory exchange not supported on {sys.platform}")


def _swap_macos(path_a: str, path_b: str) -> None:
    """Swap two paths on macOS using ``renamex_np`` with ``RENAME_SWAP``."""
    libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    try:
        func = libc.renamex_np
    except AttributeError as exc:
        raise RuntimeError("renamex_np not available on this macOS version") from exc

    func.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    func.restype = ctypes.c_int
    result = func(
        os.fsencode(path_a),
        os.fsencode(path_b),
        _RENAME_SWAP_FLAG,
    )
    if result != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno), path_a, path_b)


def _swap_linux(path_a: str, path_b: str) -> None:
    """Swap two paths on Linux using ``renameat2`` with ``RENAME_EXCHANGE``."""
    libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    try:
        func = libc.renameat2
    except AttributeError as exc:
        raise RuntimeError("renameat2 not available on this Linux version") from exc

    func.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    func.restype = ctypes.c_int
    result = func(
        _AT_FDCWD,
        os.fsencode(path_a),
        _AT_FDCWD,
        os.fsencode(path_b),
        _RENAME_SWAP_FLAG,
    )
    if result != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno), path_a, path_b)


class OutputStagingError(Exception):
    """Raised when a staging operation violates containment or registration.

    This covers: atomic-exchange unavailability, unregistered/external/
    moved/symlinked/wrong-parent staging paths, and similar safety
    violations at mutation boundaries.
    """


class OutputStagingService:
    """Manages candidate output staging and atomic publication.

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

        # Verify the staging directory stays within the containment boundary.
        try:
            staging_dir.resolve().relative_to(self._repo_root)
        except ValueError as exc:
            raise OutputContainmentError(
                f"staging directory escapes repo root: {staging_dir}"
            ) from exc

        staging_dir.mkdir(parents=True, exist_ok=False)
        resolved = staging_dir.resolve()
        self._registered_staging[resolved] = _st_identity(staging_dir)
        return staging_dir

    # --- Registration verification ---------------------------------------

    # TOCTOU boundary: _verify_registered reads the filesystem identity at
    # check time, but between this check and the subsequent mutation
    # (rmtree / rename / swap) the path could be replaced by another process
    # on the same machine.  This is a local-concurrency TOCTOU race that
    # cannot be eliminated without fd-based operations (e.g. openat with
    # O_NOFOLLOW).  The current implementation does not attempt fd-based
    # hardening; the identity check reduces the attack surface but does not
    # provide a guarantee.

    def _verify_registered(self, staging_dir: Path) -> None:
        """Verify *staging_dir* was created by this service and is safe.

        Rejects symlinks, unregistered paths, wrong-parent paths, and
        paths whose ``(st_dev, st_ino)`` differs from creation time
        (moved or replaced).

        Raises:
            OutputStagingError: If any safety check fails.
        """
        # Reject symlinks before any other check.  A symlink at the
        # staging path is not a real staging directory and must not be
        # mutated via rmtree or rename.
        if staging_dir.is_symlink():
            raise OutputStagingError(
                f"staging directory is a symlink (refusing to mutate): {staging_dir}"
            )

        resolved = staging_dir.resolve()
        if resolved not in self._registered_staging:
            raise OutputStagingError(
                f"staging directory was not created by this service "
                f"(unregistered): {staging_dir}"
            )

        expected_parent = self._staging_parent.resolve()
        if resolved.parent != expected_parent:
            raise OutputStagingError(
                f"staging directory has wrong parent (moved or external): "
                f"{staging_dir} (expected {expected_parent}, "
                f"got {resolved.parent})"
            )

        # If the path still exists, verify (st_dev, st_ino) matches the
        # identity recorded at creation time.  This catches
        # replacement-by-another-directory at the same path but does not
        # eliminate the TOCTOU window between this check and the
        # subsequent mutation.
        if staging_dir.exists():
            expected_identity = self._registered_staging[resolved]
            actual_identity = _st_identity(staging_dir)
            if expected_identity != actual_identity:
                raise OutputStagingError(
                    f"staging directory identity mismatch (path was replaced "
                    f"or moved): {staging_dir}"
                )

    def _deregister(self, staging_dir: Path) -> None:
        """Remove a staging path from the registration set."""
        self._registered_staging.pop(staging_dir.resolve(), None)

    # --- Publication -----------------------------------------------------

    def publish(self, staging_dir: Path) -> list[Diagnostic]:
        """Atomically replace final output with the staging directory.

        When final output already exists, a true atomic directory exchange
        swaps staging and final so that final never disappears or exposes
        a partial tree.  When final does not exist, a single atomic
        ``os.rename`` is used.

        If atomic exchange is unavailable on the platform, this method
        raises :class:`OutputStagingError` *before* changing final.

        After a successful exchange the old tree (now at the staging path)
        is cleaned up; cleanup failure produces a warning diagnostic and
        never corrupts the new final.  Registration is retained on
        cleanup failure so that cleanup can be retried safely.

        Returns:
            A list of warning :class:`Diagnostic` instances (e.g. from
            post-exchange cleanup).  Empty on a clean success.

        Raises:
            FileNotFoundError: If *staging_dir* does not exist.
            OutputStagingError: If the path is unregistered, external,
                moved, symlinked, wrong-parent, or if atomic exchange is
                unavailable or fails.
        """
        self._verify_registered(staging_dir)

        if not staging_dir.exists():
            raise FileNotFoundError(f"Staging directory not found: {staging_dir}")

        if not self._output.exists():
            # Final does not exist -- single atomic rename.
            os.rename(staging_dir, self._output)
            self._deregister(staging_dir)
            return []

        # Final exists -- true atomic directory exchange.
        try:
            _atomic_swap(str(staging_dir), str(self._output))
        except RuntimeError as exc:
            raise OutputStagingError(
                f"Atomic directory exchange unavailable; final output unchanged: {exc}"
            ) from exc
        except OSError as exc:
            raise OutputStagingError(
                f"Atomic directory exchange failed; final output unchanged: {exc}"
            ) from exc

        # Swap succeeded: final has new content, staging path has old tree.
        # Update registration to the old tree now at the staging path before
        # cleanup; if old-tree cleanup fails, retain registration so cleanup
        # can be retried safely, and only retire after successful deletion.
        resolved = staging_dir.resolve()
        if staging_dir.exists():
            self._registered_staging[resolved] = _st_identity(staging_dir)

        # Best-effort cleanup of the old tree (now at the staging path).
        warnings: list[Diagnostic] = []
        try:
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
            self._deregister(staging_dir)
        except OSError:
            logger.warning("old_tree_cleanup_failed", path=str(staging_dir))
            warnings.append(
                Diagnostic(
                    severity="warning",
                    code="OLD_TREE_CLEANUP_FAILED",
                    message=(
                        f"Failed to clean up old output tree after "
                        f"atomic exchange: {staging_dir}"
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
