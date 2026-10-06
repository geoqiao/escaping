"""Output-path containment validation.

Before any deletion or rendering, the configured output path must pass a
containment safety check.  This module provides the public validation
interface.  It rejects the filesystem root, repository root, current directory,
parent directories, absolute escapes, **all** symlinks (``shutil.rmtree``
cannot safely operate on a symbolic link), and Git's own directory.

The validator reads the filesystem to detect symlinks but performs **no
mutation** - it never creates, deletes, or modifies files or directories.
"""

from __future__ import annotations

from pathlib import Path


class OutputContainmentError(ValueError):
    """Raised when an output path fails containment validation."""


def validate_output_containment(
    output: str | Path,
    repo_root: Path,
    name: str = "--output",
) -> Path:
    """Validate that *output* is safely contained within *repo_root*.

    Parameters
    ----------
    output:
        The configured output path (relative string or ``Path``).
    repo_root:
        The repository root directory used as the containment boundary.
    name:
        What error messages call the path, such as the Config field.

    Returns
    -------
    Path
        The resolved absolute output path if validation passes.

    Raises
    ------
    OutputContainmentError
        If the path is absolute, identifies the filesystem root, the
        repository root, the current directory, a parent directory, is
        outside the allowed output-root set, or contains **any** symlink
        component (even one resolving inside the repository).

    Notes
    -----
    This function reads the filesystem (``is_symlink``, ``resolve``) to
    detect symlinks but does **not** create, delete, or modify any file or
    directory.
    """
    output_path = Path(output)

    # --- Reject filesystem root ------------------------------------------------
    if str(output_path) == "/":
        raise OutputContainmentError(f"{name} must not be the filesystem root")

    # --- Reject absolute paths ------------------------------------------------
    if output_path.is_absolute():
        raise OutputContainmentError(f"{name} must be a relative path")

    parts = output_path.parts

    # --- Reject filesystem root, current directory, and empty string ---------
    if not parts or parts == (".",) or parts == ("/",):
        raise OutputContainmentError(
            f"{name} must not be the repository root, filesystem root, "
            "or current directory"
        )

    # --- Reject parent-directory escapes --------------------------------------
    if ".." in parts:
        raise OutputContainmentError(
            f"{name} must not contain parent-directory references (..)"
        )

    # --- Reject Git's own directory -----------------------------------------
    if ".git" in parts:
        raise OutputContainmentError(f"{name} must not be inside .git")

    # --- Resolve repo_root to an absolute path without symlinks --------------
    try:
        repo_resolved = repo_root.resolve()
    except (RuntimeError, OSError):
        raise OutputContainmentError(
            "symlink resolution loop while resolving the repository root"
        ) from None

    # --- Walk existing path components to reject ALL symlinks ----------------
    # shutil.rmtree cannot safely operate on a symbolic link: it raises
    # OSError("Cannot call rmtree on a symbolic link").  Every symlink
    # component is therefore rejected regardless of where it resolves.
    current = repo_resolved
    for part in parts:
        current = current / part
        if current.is_symlink():
            try:
                current.resolve()  # Raises on a symlink loop.
            except (RuntimeError, OSError):
                raise OutputContainmentError(
                    f"{name} passes through a symlink with a resolution loop"
                ) from None
            raise OutputContainmentError(f"{name} must not pass through a symlink")

    # --- Final resolved-path containment check -------------------------------
    try:
        resolved = (repo_root / output_path).resolve()
    except (RuntimeError, OSError):
        raise OutputContainmentError(
            f"symlink resolution loop while resolving {name}"
        ) from None

    if resolved == repo_resolved:
        raise OutputContainmentError(f"{name} resolves to the repository root")

    try:
        resolved.relative_to(repo_resolved)
    except ValueError:
        raise OutputContainmentError(f"{name} escapes the repository root") from None

    return resolved
