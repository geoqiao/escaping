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
        raise OutputContainmentError(
            f"output path must not be the filesystem root: {output}"
        )

    # --- Reject absolute paths ------------------------------------------------
    if output_path.is_absolute():
        raise OutputContainmentError(
            f"output path must be relative, got absolute path: {output}"
        )

    parts = output_path.parts

    # --- Reject filesystem root, current directory, and empty string ---------
    if not parts or parts == (".",) or parts == ("/",):
        raise OutputContainmentError(
            f"output path must not be the repository root, filesystem root, "
            f"or current directory: {output!r}"
        )

    # --- Reject parent-directory escapes --------------------------------------
    if ".." in parts:
        raise OutputContainmentError(
            f"output path must not contain parent-directory references (..): {output}"
        )

    # --- Reject roots outside the allowed output-root set --------------------
    top_level = parts[0]
    if top_level not in ALLOWED_OUTPUT_ROOTS:
        if top_level in PROTECTED_ROOTS:
            raise OutputContainmentError(
                f"output root {top_level!r} is a protected repository root "
                f"and is not in the allowed set {sorted(ALLOWED_OUTPUT_ROOTS)}"
            )
        raise OutputContainmentError(
            f"output root {top_level!r} is not in the allowed set "
            f"{sorted(ALLOWED_OUTPUT_ROOTS)}"
        )

    # --- Resolve repo_root to an absolute path without symlinks --------------
    try:
        repo_resolved = repo_root.resolve()
    except (RuntimeError, OSError) as e:
        raise OutputContainmentError(
            f"symlink resolution loop detected while resolving repo root: "
            f"{repo_root} ({e})"
        ) from e

    # --- Walk existing path components to reject ALL symlinks ----------------
    # shutil.rmtree cannot safely operate on a symbolic link: it raises
    # OSError("Cannot call rmtree on a symbolic link").  Every symlink
    # component is therefore rejected regardless of where it resolves.
    current = repo_resolved
    for part in parts:
        current = current / part
        if current.is_symlink():
            try:
                link_target = current.resolve()
            except (RuntimeError, OSError) as e:
                raise OutputContainmentError(
                    f"output path contains a symlink with a resolution loop: "
                    f"{current} ({e})"
                ) from e
            raise OutputContainmentError(
                f"output path contains a symlink: {current} -> {link_target}"
            )

    # --- Final resolved-path containment check -------------------------------
    try:
        resolved = (repo_root / output_path).resolve()
    except (RuntimeError, OSError) as e:
        raise OutputContainmentError(
            f"symlink resolution loop detected while resolving output path: "
            f"{output} ({e})"
        ) from e

    if resolved == repo_resolved:
        raise OutputContainmentError(
            f"output path resolves to the repository root: {output}"
        )

    try:
        resolved.relative_to(repo_resolved)
    except ValueError:
        raise OutputContainmentError(
            f"output path escapes the repository root: {output}"
        ) from None

    return resolved


def validate_output_child_name(name: str, field_name: str = "name") -> str:
    """Validate a child path/name field as a safe single name/filename.

    Ensures that *name* is a single path component with no separators,
    absolute prefixes, or ``.`` / ``..`` references so it cannot escape the
    validated output directory.

    Parameters
    ----------
    name:
        The configured child path/name (e.g. ``blog``, ``atom.xml``).
    field_name:
        Human-readable field name used in error messages.

    Returns
    -------
    str
        The validated name unchanged.

    Raises
    ------
    OutputContainmentError
        If *name* is empty, absolute, contains path separators, or is
        ``.`` / ``..``.
    """
    if not name or not name.strip():
        raise OutputContainmentError(
            f"{field_name} must not be empty or blank: {name!r}"
        )

    if Path(name).is_absolute():
        raise OutputContainmentError(
            f"{field_name} must not be an absolute path: {name!r}"
        )

    if "/" in name or "\\" in name:
        raise OutputContainmentError(
            f"{field_name} must not contain path separators: {name!r}"
        )

    if name in (".", ".."):
        raise OutputContainmentError(f"{field_name} must not be '.' or '..': {name!r}")

    return name
