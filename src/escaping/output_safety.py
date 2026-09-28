"""Output-path containment validation.

Before any deletion or rendering, the configured output path must pass a
containment safety check.  This module provides the public validation
interface.  It rejects the filesystem root, repository root, current directory,
parent directories, absolute escapes, **all** symlinks (``shutil.rmtree``
cannot safely operate on a symbolic link), and roots outside an explicit
allowed set.

The validator reads the filesystem to detect symlinks but performs **no
mutation** - it never creates, deletes, or modifies files or directories.
"""

from __future__ import annotations

from pathlib import Path

#: Conservative set of allowed top-level output-root names suitable for
#: generated sites.  A configured output path must have its first component
#: in this set.
ALLOWED_OUTPUT_ROOTS: frozenset[str] = frozenset(
    {"output", "_site", "public", "dist", "build"}
)

#: Repository roots that must never be used as an output directory.
#: These are subsumed by the allowed-set check (they are not in
#: ``ALLOWED_OUTPUT_ROOTS``) but are listed explicitly for clarity.
PROTECTED_ROOTS: frozenset[str] = frozenset({".git", "src", "tests", "templates"})


class OutputContainmentError(ValueError):
    """Raised when an output path fails containment validation."""


def validate_output_containment(
    output: str | Path,
    repo_root: Path,
) -> Path:
    """Validate that *output* is safely contained within *repo_root*.

    Parameters
    ----------
    output:
        The configured output path (relative string or ``Path``).
    repo_root:
        The repository root directory used as the containment boundary.

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
        raise OutputContainmentError("paths.output must not be the filesystem root")

    # --- Reject absolute paths ------------------------------------------------
    if output_path.is_absolute():
        raise OutputContainmentError("paths.output must be a relative path")

    parts = output_path.parts

    # --- Reject filesystem root, current directory, and empty string ---------
    if not parts or parts == (".",) or parts == ("/",):
        raise OutputContainmentError(
            "paths.output must not be the repository root, filesystem root, "
            "or current directory"
        )

    # --- Reject parent-directory escapes --------------------------------------
    if ".." in parts:
        raise OutputContainmentError(
            "paths.output must not contain parent-directory references (..)"
        )

    # --- Reject roots outside the allowed output-root set --------------------
    top_level = parts[0]
    if top_level not in ALLOWED_OUTPUT_ROOTS:
        if top_level in PROTECTED_ROOTS:
            raise OutputContainmentError(
                "paths.output must not be inside a protected repository folder; "
                f"allowed folders: {', '.join(sorted(ALLOWED_OUTPUT_ROOTS))}"
            )
        raise OutputContainmentError(
            "paths.output must start with an allowed folder: "
            f"{', '.join(sorted(ALLOWED_OUTPUT_ROOTS))}"
        )

    # --- Resolve repo_root to an absolute path without symlinks --------------
    try:
        repo_resolved = repo_root.resolve()
    except RuntimeError, OSError:
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
            except RuntimeError, OSError:
                raise OutputContainmentError(
                    "paths.output passes through a symlink with a resolution loop"
                ) from None
            raise OutputContainmentError("paths.output must not pass through a symlink")

    # --- Final resolved-path containment check -------------------------------
    try:
        resolved = (repo_root / output_path).resolve()
    except RuntimeError, OSError:
        raise OutputContainmentError(
            "symlink resolution loop while resolving paths.output"
        ) from None

    if resolved == repo_resolved:
        raise OutputContainmentError("paths.output resolves to the repository root")

    try:
        resolved.relative_to(repo_resolved)
    except ValueError:
        raise OutputContainmentError(
            "paths.output escapes the repository root"
        ) from None

    return resolved
