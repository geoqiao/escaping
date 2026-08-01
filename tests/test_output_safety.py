"""Output containment safety tests.

The containment validator rejects dangerous output paths before any filesystem
mutation (deletion or rendering).  It reads the filesystem to detect symlink
components but performs no mutation itself.

Rejected paths:
- Filesystem root (``/``)
- Repository root (``.``)
- Current directory / empty string
- Parent directory (``..``)
- Absolute paths (``/tmp/evil``)
- Paths with ``..`` components (``output/../../etc``)
- **Any** symlink component (even those resolving inside the repo), matching
  ``shutil.rmtree`` semantics.
- Roots outside the explicit allowed output-root set.
- Protected repository roots (``.git``, ``src``, ``tests``, ``templates``).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from github_blog.output_safety import (
    ALLOWED_OUTPUT_ROOTS,
    PROTECTED_ROOTS,
    OutputContainmentError,
    validate_output_child_name,
    validate_output_containment,
)


class TestRejectUnsafePaths:
    """Paths that must be rejected before mutation."""

    def test_reject_filesystem_root(self, tmp_path: Path) -> None:
        with pytest.raises(OutputContainmentError, match="root"):
            validate_output_containment("/", tmp_path)

    def test_reject_repository_root_dot(self, tmp_path: Path) -> None:
        with pytest.raises(OutputContainmentError, match="root"):
            validate_output_containment(".", tmp_path)

    def test_reject_empty_string(self, tmp_path: Path) -> None:
        with pytest.raises(OutputContainmentError, match="root"):
            validate_output_containment("", tmp_path)

    def test_reject_parent_directory(self, tmp_path: Path) -> None:
        with pytest.raises(OutputContainmentError, match="parent"):
            validate_output_containment("..", tmp_path)

    def test_reject_absolute_path(self, tmp_path: Path) -> None:
        with pytest.raises(OutputContainmentError, match=r"absolute|relative"):
            validate_output_containment("/tmp/evil", tmp_path)  # noqa: S108

    def test_reject_absolute_path_existing(self, tmp_path: Path) -> None:
        with pytest.raises(OutputContainmentError, match=r"absolute|relative"):
            validate_output_containment("/etc", tmp_path)

    def test_reject_dotdot_in_path(self, tmp_path: Path) -> None:
        with pytest.raises(OutputContainmentError, match="parent"):
            validate_output_containment("output/../../etc", tmp_path)

    def test_reject_dotdot_prefix(self, tmp_path: Path) -> None:
        with pytest.raises(OutputContainmentError, match="parent"):
            validate_output_containment("../output", tmp_path)

    def test_reject_dotdot_suffix(self, tmp_path: Path) -> None:
        with pytest.raises(OutputContainmentError, match="parent"):
            validate_output_containment("output/..", tmp_path)


class TestAllowedOutputRoots:
    """Only paths whose top-level component is in the allowed set are accepted."""

    def test_allowed_set_contains_expected_roots(self) -> None:
        assert "output" in ALLOWED_OUTPUT_ROOTS
        assert "_site" in ALLOWED_OUTPUT_ROOTS
        assert "public" in ALLOWED_OUTPUT_ROOTS
        assert "dist" in ALLOWED_OUTPUT_ROOTS
        assert "build" in ALLOWED_OUTPUT_ROOTS

    def test_protected_roots_are_explicit(self) -> None:
        assert ".git" in PROTECTED_ROOTS
        assert "src" in PROTECTED_ROOTS
        assert "tests" in PROTECTED_ROOTS
        assert "templates" in PROTECTED_ROOTS

    @pytest.mark.parametrize("root", sorted(ALLOWED_OUTPUT_ROOTS))
    def test_accept_allowed_root(self, tmp_path: Path, root: str) -> None:
        result = validate_output_containment(root, tmp_path)
        assert result == (tmp_path / root).resolve()

    def test_accept_nested_inside_allowed_root(self, tmp_path: Path) -> None:
        result = validate_output_containment("output/site", tmp_path)
        assert result == (tmp_path / "output" / "site").resolve()

    @pytest.mark.parametrize("root", sorted(PROTECTED_ROOTS))
    def test_reject_protected_root(self, tmp_path: Path, root: str) -> None:
        with pytest.raises(OutputContainmentError, match="allowed"):
            validate_output_containment(root, tmp_path)

    def test_reject_root_outside_allowed_set(self, tmp_path: Path) -> None:
        with pytest.raises(OutputContainmentError, match="allowed"):
            validate_output_containment("my_custom_output", tmp_path)

    def test_reject_nested_protected_root(self, tmp_path: Path) -> None:
        # Even though the top-level "output" is allowed, a protected root
        # as a deeper component should still be checked via the containment
        # logic.  However, the allowed-set check is only on the top-level
        # component.  The path "output/src" is allowed (it's inside output).
        # This test verifies that a top-level protected root is rejected.
        with pytest.raises(OutputContainmentError, match="allowed"):
            validate_output_containment("src", tmp_path)


class TestRejectAllSymlinks:
    """All symlink components must be rejected, even those resolving inside the repo."""

    def test_reject_symlink_to_outside(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "escape_target_symlink"
        outside.mkdir(exist_ok=True)
        link = tmp_path / "output"
        os.symlink(outside, link)

        with pytest.raises(OutputContainmentError, match="symlink"):
            validate_output_containment("output", tmp_path)

    def test_reject_nested_symlink_escape(self, tmp_path: Path) -> None:
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        outside = tmp_path.parent / "escape_target_nested"
        outside.mkdir(exist_ok=True)
        link = build_dir / "output"
        os.symlink(outside, link)

        with pytest.raises(OutputContainmentError, match="symlink"):
            validate_output_containment("build/output", tmp_path)

    def test_reject_symlink_within_repo(self, tmp_path: Path) -> None:
        """A symlink that stays within repo_root is STILL rejected.

        ``shutil.rmtree`` cannot safely operate on a symlink as an output
        root (it raises ``OSError`` for symbolic links), so all symlinks
        must be rejected regardless of where they resolve.
        """
        target = tmp_path / "real_output"
        target.mkdir()
        link = tmp_path / "output"
        os.symlink(target, link)

        with pytest.raises(OutputContainmentError, match="symlink"):
            validate_output_containment("output", tmp_path)

    def test_reject_symlink_resolution_loop(self, tmp_path: Path) -> None:
        """A symlink-resolution loop must report OutputContainmentError.

        Two symlinks pointing at each other form a loop.  ``Path.resolve``
        raises ``RuntimeError`` / ``OSError`` for such loops; the validator
        must catch that and report ``OutputContainmentError`` instead of
        letting the raw exception propagate.
        """
        link_a = tmp_path / "output"
        link_b = tmp_path / "loop_target"
        os.symlink(link_b, link_a)
        os.symlink(link_a, link_b)

        with pytest.raises(OutputContainmentError, match="symlink"):
            validate_output_containment("output", tmp_path)


class TestAcceptSafePaths:
    """Safe relative paths must be accepted."""

    def test_accept_simple_output(self, tmp_path: Path) -> None:
        result = validate_output_containment("output", tmp_path)
        assert result == (tmp_path / "output").resolve()

    def test_accept_nested_output(self, tmp_path: Path) -> None:
        result = validate_output_containment("build/site", tmp_path)
        assert result == (tmp_path / "build" / "site").resolve()

    def test_accept_output_with_trailing_slash(self, tmp_path: Path) -> None:
        result = validate_output_containment("output/", tmp_path)
        assert result is not None

    def test_accept_existing_output_dir(self, tmp_path: Path) -> None:
        (tmp_path / "output").mkdir()
        result = validate_output_containment("output", tmp_path)
        assert result == (tmp_path / "output").resolve()

    def test_returns_resolved_path(self, tmp_path: Path) -> None:
        result = validate_output_containment("output", tmp_path)
        assert result.is_absolute()


class TestNoFilesystemMutation:
    """The validator must not create, delete, or modify any files."""

    def test_does_not_create_output_dir(self, tmp_path: Path) -> None:
        validate_output_containment("output", tmp_path)
        assert not (tmp_path / "output").exists()

    def test_does_not_modify_existing_files(self, tmp_path: Path) -> None:
        existing = tmp_path / "existing.txt"
        existing.write_text("original")
        (tmp_path / "output").mkdir()
        marker = tmp_path / "output" / "marker.txt"
        marker.write_text("keep me")

        validate_output_containment("output", tmp_path)

        assert existing.read_text() == "original"
        assert marker.read_text() == "keep me"

    def test_does_not_delete_on_rejection(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "output"
        out_dir.mkdir()
        (out_dir / "file.txt").write_text("keep")

        with pytest.raises(OutputContainmentError):
            validate_output_containment("..", tmp_path)

        assert (out_dir / "file.txt").exists()
        assert (out_dir / "file.txt").read_text() == "keep"


class TestValidateOutputChildName:
    """Child path/name fields must be safe single names/filenames."""

    def test_accepts_simple_name(self) -> None:
        assert validate_output_child_name("blog", "blog") == "blog"

    def test_accepts_filename(self) -> None:
        assert validate_output_child_name("atom.xml", "rss") == "atom.xml"

    def test_accepts_theme_name(self) -> None:
        assert validate_output_child_name("Escape1", "theme") == "Escape1"

    def test_rejects_empty(self) -> None:
        with pytest.raises(OutputContainmentError, match="empty"):
            validate_output_child_name("", "rss")

    def test_rejects_absolute_path(self) -> None:
        with pytest.raises(OutputContainmentError, match="absolute"):
            validate_output_child_name("/etc/passwd", "rss")

    def test_rejects_forward_slash(self) -> None:
        with pytest.raises(OutputContainmentError, match="separator"):
            validate_output_child_name("foo/bar", "blog")

    def test_rejects_backslash(self) -> None:
        with pytest.raises(OutputContainmentError, match="separator"):
            validate_output_child_name("foo\\bar", "blog")

    def test_rejects_dot(self) -> None:
        with pytest.raises(OutputContainmentError, match=r"'\.'|dot"):
            validate_output_child_name(".", "blog")

    def test_rejects_dotdot(self) -> None:
        with pytest.raises(OutputContainmentError, match=r"\.\.|dot"):
            validate_output_child_name("..", "blog")

    def test_rejects_dotdot_in_name(self) -> None:
        with pytest.raises(OutputContainmentError, match="separator"):
            validate_output_child_name("../evil", "blog")
