"""Output containment safety tests.

The validator rejects dangerous output paths before any filesystem mutation.
It reads the filesystem to detect symlink components but performs no mutation.

Rejected: filesystem root, repo root, parent dirs, absolute paths, paths with
``..`` components, any symlink component (even inside-repo), roots outside the
allowed set, protected repo roots.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from escaping.output_safety import (
    OutputContainmentError,
    validate_output_child_name,
    validate_output_containment,
)

# Hardcoded expectations — NOT imported from implementation constants.
_ALLOWED_ROOTS = ["_site", "build", "dist", "output", "public"]
_PROTECTED_ROOTS = [".git", "src", "templates", "tests"]


# ---------------------------------------------------------------------------
# Unsafe paths rejected
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path, match",
    [
        ("/", "root"),
        (".", "root"),
        ("", "root"),
        ("..", "parent"),
        ("/tmp/evil", "absolute|relative"),  # noqa: S108
        ("/etc", "absolute|relative"),
        ("output/../../etc", "parent"),
        ("../output", "parent"),
        ("output/..", "parent"),
    ],
    ids=[
        "fs-root",
        "dot",
        "empty",
        "parent",
        "abs",
        "abs-existing",
        "dotdot-mid",
        "dotdot-prefix",
        "dotdot-suffix",
    ],
)
def test_reject_unsafe_paths(tmp_path: Path, path: str, match: str) -> None:
    with pytest.raises(OutputContainmentError, match=match):
        validate_output_containment(path, tmp_path)


@pytest.mark.parametrize("root", _ALLOWED_ROOTS)
def test_accept_allowed_roots(tmp_path: Path, root: str) -> None:
    result = validate_output_containment(root, tmp_path)
    assert result == (tmp_path / root).resolve()


def test_accept_nested_inside_allowed_root(tmp_path: Path) -> None:
    assert (
        validate_output_containment("output/site", tmp_path)
        == (tmp_path / "output" / "site").resolve()
    )


@pytest.mark.parametrize("root", _PROTECTED_ROOTS)
def test_reject_protected_roots(tmp_path: Path, root: str) -> None:
    with pytest.raises(OutputContainmentError, match="allowed"):
        validate_output_containment(root, tmp_path)


def test_reject_root_outside_allowed_set(tmp_path: Path) -> None:
    with pytest.raises(OutputContainmentError, match="allowed"):
        validate_output_containment("my_custom_output", tmp_path)


# ---------------------------------------------------------------------------
# Symlink rejection (all types, including loops)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path, setup",
    [
        # Symlink pointing outside repo
        ("output", lambda tp: _symlink(tp, "output", tp.parent / "escape1")),
        # Nested symlink escape (symlink at build/output)
        (
            "build/output",
            lambda tp: (
                (tp / "build").mkdir(),
                _symlink(tp / "build", "output", tp.parent / "escape2"),
            ),
        ),
        # Symlink that stays within repo (still rejected)
        (
            "output",
            lambda tp: (
                (tp / "real_output").mkdir(),
                _symlink(tp, "output", tp / "real_output"),
            ),
        ),
    ],
    ids=["outside", "nested", "within-repo"],
)
def test_reject_symlink(
    tmp_path: Path, path: str, setup: Callable[[Path], None]
) -> None:
    setup(tmp_path)
    with pytest.raises(OutputContainmentError, match="symlink"):
        validate_output_containment(path, tmp_path)


def test_reject_symlink_resolution_loop(tmp_path: Path) -> None:
    link_a = tmp_path / "output"
    link_b = tmp_path / "loop_target"
    os.symlink(link_b, link_a)
    os.symlink(link_a, link_b)
    with pytest.raises(OutputContainmentError, match="symlink"):
        validate_output_containment("output", tmp_path)


def _symlink(parent: Path, name: str, target: Path) -> None:
    target.mkdir(exist_ok=True)
    os.symlink(target, parent / name)


# ---------------------------------------------------------------------------
# Safe paths accepted & no filesystem mutation
# ---------------------------------------------------------------------------


def test_accept_safe_paths(tmp_path: Path) -> None:
    assert (
        validate_output_containment("output", tmp_path)
        == (tmp_path / "output").resolve()
    )
    (tmp_path / "output").mkdir()
    assert validate_output_containment("output/", tmp_path) is not None
    assert validate_output_containment("output", tmp_path).is_absolute()


def test_no_filesystem_mutation(tmp_path: Path) -> None:
    """Validator must not create, delete, or modify files."""
    # Does not create output dir
    validate_output_containment("output", tmp_path)
    assert not (tmp_path / "output").exists()
    # Does not modify existing files
    (tmp_path / "output").mkdir()
    marker = tmp_path / "output" / "marker.txt"
    marker.write_text("keep me")
    validate_output_containment("output", tmp_path)
    assert marker.read_text() == "keep me"
    # Does not delete on rejection
    out = tmp_path / "output"
    (out / "file.txt").write_text("keep")
    with pytest.raises(OutputContainmentError):
        validate_output_containment("..", tmp_path)
    assert (out / "file.txt").read_text() == "keep"


# ---------------------------------------------------------------------------
# validate_output_child_name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name, field, ok, match",
    [
        ("blog", "blog", True, ""),
        ("atom.xml", "rss", True, ""),
        ("Escape1", "theme", True, ""),
        ("", "rss", False, "empty"),
        ("/etc/passwd", "rss", False, "absolute"),
        ("foo/bar", "blog", False, "separator"),
        ("foo\\bar", "blog", False, "separator"),
        (".", "blog", False, r"'\.'|dot"),
        ("..", "blog", False, r"\.\.|dot"),
        ("../evil", "blog", False, "separator"),
    ],
    ids=[
        "blog",
        "filename",
        "theme",
        "empty",
        "absolute",
        "fslash",
        "bslash",
        "dot",
        "dotdot",
        "dotdot-name",
    ],
)
def test_validate_output_child_name(
    name: str, field: str, ok: bool, match: str
) -> None:
    if ok:
        assert validate_output_child_name(name, field) == name
    else:
        with pytest.raises(OutputContainmentError, match=match):
            validate_output_child_name(name, field)
