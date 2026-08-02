"""Tests for Ticket 03: stage output without risking the current site.

Covers BuildResult/Diagnostic, BasicArtifactValidator, OutputStagingService
(staging creation, atomic publish, cleanup), and BlogGenerator integration
(failure preserves previous output byte-for-byte).

Critical regressions: atomic swap failure preservation, post-swap cleanup
retry, replaced-inode rejection, no intermediate state on swap failure.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
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

if TYPE_CHECKING:
    from github_blog.cli import BlogGenerator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_issue(
    number: int, title: str = "Test Post", labels: list[str] | None = None
) -> MagicMock:
    issue = MagicMock()
    issue.number = number
    issue.title = title
    issue.body = "body"
    issue.labels = [MagicMock(name=label) for label in (labels or [])]
    issue.created_at = datetime(2024, 1, number, tzinfo=timezone.utc)
    issue.updated_at = datetime(2024, 1, number, tzinfo=timezone.utc)
    return issue


def _make_settings(tmp_path: Path, output: str = "output") -> Settings:
    config = f"""
github:
  repo: user/repo
  allowed_authors: [user]
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
    p = tmp_path / "config.yaml"
    p.write_text(config)
    return Settings.load_from_yaml(p)


def _hash_dir(path: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(path.rglob("*")):
        if f.is_file():
            h.update(str(f.relative_to(path)).encode())
            h.update(f.read_bytes())
    return h.hexdigest()


def _prev_output(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text("old index", encoding="utf-8")
    (d / "blog").mkdir(exist_ok=True)
    (d / "blog" / "old-post.html").write_text("old post", encoding="utf-8")
    (d / "marker.txt").write_text("survive", encoding="utf-8")


def _setup_theme(tmp_path: Path) -> None:
    (tmp_path / "templates" / "Escape1").mkdir(parents=True)


def _no_staging(parent: Path) -> None:
    assert not [p for p in parent.iterdir() if ".staging." in p.name]


def _fake_github(
    issues: list[MagicMock] | None = None, *, fail: bool = False
) -> MagicMock:
    gh = MagicMock()
    if fail:
        gh.get_repo.side_effect = RuntimeError("GitHub API error")
    else:
        gh.get_repo.return_value = MagicMock()
        gh.get_user_issues.return_value = issues or []
    return gh


def _fake_render(*, fail_md: bool = False, fail_render: bool = False) -> MagicMock:
    r = MagicMock()
    r.markdown_to_html.return_value = "<p>body</p>"
    r.render_post.return_value = "<html><body>body</body></html>"
    r.render_index.return_value = "<html><body>index</body></html>"
    r.render_home.return_value = "<html><body>home</body></html>"
    r.render_tag_page.return_value = "<html><body>tag</body></html>"
    r.render_tags_page.return_value = "<html><body>tags</body></html>"
    r.generate_rss.return_value = '<?xml version="1.0"?><feed></feed>'
    r.render_sitemap.return_value = '<?xml version="1.0"?><urlset></urlset>'
    r.render_robots.return_value = "User-agent: *\nDisallow:"
    r.render_about.return_value = "<html><body>about</body></html>"
    if fail_md:
        r.markdown_to_html.side_effect = RuntimeError("md failed")
    if fail_render:
        r.render_post.side_effect = RuntimeError("render failed")
    return r


def _make_gen(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    settings: Settings | None = None,
    gh: MagicMock | None = None,
    render: MagicMock | None = None,
    validator: MagicMock | None = None,
    staging: MagicMock | None = None,
    setup_theme: bool = True,
) -> BlogGenerator:
    from github_blog.cli import BlogGenerator

    monkeypatch.chdir(tmp_path)
    if setup_theme:
        _setup_theme(tmp_path)
    s = settings or _make_settings(tmp_path)
    return BlogGenerator(
        "fake-token",
        "user/repo",
        s,
        github_service=gh or _fake_github([_mock_issue(1)]),
        render_service=render or _fake_render(),
        artifact_validator=validator,
        output_staging=staging,
    )


# ---------------------------------------------------------------------------
# BuildResult / Diagnostic
# ---------------------------------------------------------------------------


def test_build_result_and_diagnostic() -> None:
    assert BuildResult(success=True).diagnostics == ()
    diag = Diagnostic(
        severity="error", code="X", message="m", issue_number=42, field="slug"
    )
    r = BuildResult(success=False, diagnostics=(diag,))
    assert r.diagnostics[0].code == "X" and r.diagnostics[0].issue_number == 42
    assert Diagnostic(severity="error", code="X", message="m").issue_number is None
    with pytest.raises(ValueError, match="severity"):
        Diagnostic(severity="info", code="X", message="m")


@pytest.mark.parametrize(
    "obj, attr",
    [
        (Diagnostic(severity="error", code="X", message="m"), "code"),
        (BuildResult(success=True), "success"),
    ],
    ids=["diagnostic", "build_result"],
)
def test_frozen_build_models_reject_mutation(obj: object, attr: str) -> None:
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(obj, attr, "mutated")


# ---------------------------------------------------------------------------
# BasicArtifactValidator
# ---------------------------------------------------------------------------


def test_artifact_validator(tmp_path: Path) -> None:
    s = _make_settings(tmp_path)
    v = BasicArtifactValidator(settings=s)
    # Missing index.html -> error
    diagnostics = v.validate(tmp_path)
    assert len(diagnostics) == 1
    assert (diagnostics[0].code, diagnostics[0].severity) == (
        "MISSING_REQUIRED_ARTIFACT",
        "error",
    )
    # Valid
    (tmp_path / "index.html").write_text("ok", encoding="utf-8")
    assert v.validate(tmp_path) == []
    # Directory named as artifact -> still fails
    (tmp_path / "index.html").unlink()
    (tmp_path / "index.html").mkdir()
    assert any(d.code == "MISSING_REQUIRED_ARTIFACT" for d in v.validate(tmp_path))


# ---------------------------------------------------------------------------
# OutputStagingService: staging creation
# ---------------------------------------------------------------------------


def test_create_staging_directory(tmp_path: Path) -> None:
    svc = OutputStagingService("output", tmp_path)
    a = svc.create_staging_directory()
    b = svc.create_staging_directory()
    assert a.exists() and b.exists() and a != b
    assert a.parent == (tmp_path / "output").parent
    a.resolve().relative_to(tmp_path.resolve())


# ---------------------------------------------------------------------------
# OutputStagingService: publish
# ---------------------------------------------------------------------------


def test_publish_to_empty_and_replace(tmp_path: Path) -> None:
    # Empty output -> single rename
    svc = OutputStagingService("output", tmp_path)
    staging = svc.create_staging_directory()
    (staging / "index.html").write_text("new", encoding="utf-8")
    svc.publish(staging)
    assert (tmp_path / "output" / "index.html").read_text() == "new"
    assert not staging.exists()
    # Replace existing -> old gone, new present
    final = tmp_path / "output"
    _prev_output(final)
    staging2 = svc.create_staging_directory()
    (staging2 / "index.html").write_text("newer", encoding="utf-8")
    svc.publish(staging2)
    assert (final / "index.html").read_text() == "newer"
    assert not (final / "marker.txt").exists()
    files = {p.name for p in final.iterdir() if p.is_file()}
    assert files == {"index.html"}


def test_failed_atomic_swap_preserves_both_trees(tmp_path: Path) -> None:
    """Swap failure: final keeps old content, staging keeps new, no backups."""
    svc = OutputStagingService("output", tmp_path)
    final = tmp_path / "output"
    _prev_output(final)
    old_hash = _hash_dir(final)
    staging = svc.create_staging_directory()
    (staging / "index.html").write_text("new", encoding="utf-8")

    with (
        patch(
            "github_blog.output_staging._atomic_swap", side_effect=OSError("swap fail")
        ),
        pytest.raises(OutputStagingError, match="exchange failed"),
    ):
        svc.publish(staging)

    assert _hash_dir(final) == old_hash
    assert (staging / "index.html").read_text() == "new"
    assert not [p for p in tmp_path.iterdir() if ".backup." in p.name]


def test_post_swap_cleanup_failure_is_warning(tmp_path: Path) -> None:
    """Swap succeeds but old-tree cleanup fails -> warning, final has new content."""
    svc = OutputStagingService("output", tmp_path)
    final = tmp_path / "output"
    _prev_output(final)
    staging = svc.create_staging_directory()
    (staging / "index.html").write_text("new", encoding="utf-8")

    with patch(
        "github_blog.output_staging.shutil.rmtree", side_effect=OSError("rmtree fail")
    ):
        warnings = svc.publish(staging)

    assert (final / "index.html").read_text() == "new"
    assert len(warnings) == 1 and warnings[0].code == "OLD_TREE_CLEANUP_FAILED"
    assert staging.exists() and (staging / "index.html").read_text() == "old index"
    assert staging.resolve() in svc._registered_staging


def test_post_swap_cleanup_retry_succeeds(tmp_path: Path) -> None:
    """After cleanup failure, retry succeeds and deregisters."""
    svc = OutputStagingService("output", tmp_path)
    final = tmp_path / "output"
    _prev_output(final)
    staging = svc.create_staging_directory()
    (staging / "index.html").write_text("new", encoding="utf-8")

    orig = shutil.rmtree
    count = [0]

    def flaky(path: str | Path) -> None:
        if count[0] == 0:
            count[0] += 1
            raise OSError("first fail")
        return orig(path)

    with patch("github_blog.output_staging.shutil.rmtree", side_effect=flaky):
        warnings = svc.publish(staging)
        assert warnings[0].code == "OLD_TREE_CLEANUP_FAILED"
        assert staging.exists()
        diags = svc.cleanup(staging)
        assert diags == []

    assert not staging.exists()
    assert staging.resolve() not in svc._registered_staging


def test_publish_rejects_replaced_staging_directory(tmp_path: Path) -> None:
    """Replaced staging dir (different st_dev/st_ino) is rejected by publish and cleanup."""
    svc = OutputStagingService("output", tmp_path)
    final = tmp_path / "output"
    _prev_output(final)
    old_hash = _hash_dir(final)
    staging = svc.create_staging_directory()
    (staging / "index.html").write_text("new", encoding="utf-8")
    orig_id = _st_identity(staging)

    moved = staging.parent / f"{staging.name}.moved"
    shutil.move(str(staging), str(moved))
    staging.mkdir(parents=True, exist_ok=False)
    (staging / "index.html").write_text("replaced", encoding="utf-8")
    assert _st_identity(staging) != orig_id

    with pytest.raises(OutputStagingError, match="identity mismatch"):
        svc.publish(staging)
    assert _hash_dir(final) == old_hash
    with pytest.raises(OutputStagingError, match="identity mismatch"):
        svc.cleanup(staging)
    assert staging.exists() and (staging / "index.html").read_text() == "replaced"


def test_publish_atomic_exchange_unavailable_raises(tmp_path: Path) -> None:
    svc = OutputStagingService("output", tmp_path)
    final = tmp_path / "output"
    _prev_output(final)
    old_hash = _hash_dir(final)
    staging = svc.create_staging_directory()
    (staging / "index.html").write_text("new", encoding="utf-8")

    with (
        patch(
            "github_blog.output_staging._atomic_swap",
            side_effect=RuntimeError("unsupported"),
        ),
        pytest.raises(OutputStagingError, match="unavailable"),
    ):
        svc.publish(staging)
    assert _hash_dir(final) == old_hash
    assert (staging / "index.html").read_text() == "new"


# ---------------------------------------------------------------------------
# OutputStagingService: cleanup
# ---------------------------------------------------------------------------


def test_cleanup_behaviour(tmp_path: Path) -> None:
    svc = OutputStagingService("output", tmp_path)
    final = tmp_path / "output"
    _prev_output(final)
    staging = svc.create_staging_directory()

    # Cleanup removes staging, leaves output
    svc.cleanup(staging)
    assert not staging.exists()
    assert (final / "index.html").read_text() == "old index"
    # Idempotent on already-removed path
    assert svc.cleanup(staging) == []
    # Unregistered path raises
    fake = tmp_path / "unregistered"
    fake.mkdir()
    with pytest.raises(OutputStagingError, match="unregistered"):
        svc.cleanup(fake)


def test_cleanup_surfaces_error_on_failure(tmp_path: Path) -> None:
    svc = OutputStagingService("output", tmp_path)
    staging = svc.create_staging_directory()
    (staging / "index.html").write_text("x", encoding="utf-8")
    with patch(
        "github_blog.output_staging.shutil.rmtree", side_effect=OSError("denied")
    ):
        diags = svc.cleanup(staging)
    assert len(diags) == 1 and diags[0].code == "CLEANUP_FAILED"
    assert staging.exists()


def test_publish_rejects_unregistered_and_symlinked(tmp_path: Path) -> None:
    svc = OutputStagingService("output", tmp_path)
    # Unregistered path
    fake = tmp_path / "fake_staging"
    fake.mkdir()
    (fake / "index.html").write_text("x", encoding="utf-8")
    with pytest.raises(OutputStagingError, match="unregistered"):
        svc.publish(fake)
    # External path
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
    # Symlinked path
    import os

    staging = svc.create_staging_directory()
    (staging / "index.html").write_text("new", encoding="utf-8")
    link = tmp_path / ".output.staging.symlink"
    os.symlink(staging, link)
    with pytest.raises(OutputStagingError, match="symlink"):
        svc.publish(link)


def test_unsafe_output_rejected_in_constructor(tmp_path: Path) -> None:
    with pytest.raises(OutputContainmentError):
        OutputStagingService("src", tmp_path)


# ---------------------------------------------------------------------------
# BlogGenerator integration
# ---------------------------------------------------------------------------


def test_successful_build_replaces_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    final = tmp_path / "output"
    _prev_output(final)
    gen = _make_gen(tmp_path, monkeypatch)
    result = gen.generate()
    assert result.success and result.diagnostics == ()
    assert not (final / "marker.txt").exists()
    assert (final / "index.html").exists()
    _no_staging(tmp_path)


@pytest.mark.parametrize(
    "fail_mode, expected_code, setup_theme",
    [
        ("fetch", "FETCH_FAILED", True),
        ("markdown", "MARKDOWN_CONVERT_FAILED", True),
        ("render", "RENDER_FAILED", True),
        ("validation", "VALIDATION_FAILED", True),
        ("artifact_exception", "ARTIFACT_VALIDATION_FAILED", True),
        ("publish", "PUBLISH_FAILED", True),
        ("publish_oserror", "PUBLISH_FAILED", True),
        ("containment", "OUTPUT_CONTAINMENT_FAILED", True),
        ("staging_creation", "STAGING_CREATION_FAILED", True),
        ("setup", "BUILD_SETUP_FAILED", False),
    ],
    ids=[
        "fetch",
        "markdown",
        "render",
        "validation",
        "artifact-exception",
        "publish",
        "publish-oserror",
        "containment",
        "staging",
        "setup",
    ],
)
def test_failure_preserves_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fail_mode: str,
    expected_code: str,
    setup_theme: bool,
) -> None:
    final = tmp_path / "output"
    _prev_output(final)
    old_hash = _hash_dir(final)

    if fail_mode == "containment":
        settings = _make_settings(tmp_path, output="src")
        (tmp_path / "src").mkdir(exist_ok=True)
        (tmp_path / "src" / "important.py").write_text("# important", encoding="utf-8")
        gen = _make_gen(
            tmp_path, monkeypatch, settings=settings, setup_theme=setup_theme
        )
    elif fail_mode == "staging_creation":
        staging = MagicMock(spec=OutputStagingService)
        staging.create_staging_directory.side_effect = OSError("cannot create")
        staging.cleanup.return_value = []
        gen = _make_gen(tmp_path, monkeypatch, staging=staging, setup_theme=setup_theme)
    elif fail_mode == "validation":
        v = MagicMock()
        v.validate.return_value = [
            Diagnostic(severity="error", code="VALIDATION_FAILED", message="fail")
        ]
        gen = _make_gen(tmp_path, monkeypatch, validator=v, setup_theme=setup_theme)
    elif fail_mode == "artifact_exception":
        v = MagicMock()
        v.validate.side_effect = RuntimeError("validator crashed")
        gen = _make_gen(tmp_path, monkeypatch, validator=v, setup_theme=setup_theme)
    elif fail_mode in {"publish", "publish_oserror"}:
        staging = MagicMock(spec=OutputStagingService)
        fake_staging = tmp_path / "fake_staging_publish"
        fake_staging.mkdir()
        staging.create_staging_directory.return_value = fake_staging
        staging.publish.side_effect = (
            OutputStagingError("publish fail")
            if fail_mode == "publish"
            else OSError("rename failed")
        )
        staging.cleanup.return_value = []
        gen = _make_gen(tmp_path, monkeypatch, staging=staging, setup_theme=setup_theme)
    elif fail_mode == "fetch":
        gen = _make_gen(
            tmp_path, monkeypatch, gh=_fake_github(fail=True), setup_theme=setup_theme
        )
    elif fail_mode == "markdown":
        gen = _make_gen(
            tmp_path,
            monkeypatch,
            render=_fake_render(fail_md=True),
            setup_theme=setup_theme,
        )
    elif fail_mode == "render":
        gen = _make_gen(
            tmp_path,
            monkeypatch,
            render=_fake_render(fail_render=True),
            setup_theme=setup_theme,
        )
    else:  # setup
        gen = _make_gen(tmp_path, monkeypatch, setup_theme=False)

    result = gen.generate()
    assert not result.success
    diagnostic = next(d for d in result.diagnostics if d.code == expected_code)
    assert diagnostic.severity == "error"
    assert _hash_dir(final) == old_hash
    _no_staging(tmp_path)


def test_warnings_do_not_block_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    final = tmp_path / "output"
    _prev_output(final)
    v = MagicMock()
    v.validate.return_value = [
        Diagnostic(severity="warning", code="MINOR", message="non-blocking")
    ]
    gen = _make_gen(tmp_path, monkeypatch, validator=v)
    result = gen.generate()
    assert result.success
    assert any(
        d.severity == "warning" and d.code == "MINOR" for d in result.diagnostics
    )
    assert not (final / "marker.txt").exists()
    assert (final / "index.html").exists()


# ---------------------------------------------------------------------------
# run_cli maps BuildResult to exit status
# ---------------------------------------------------------------------------


def test_run_cli_exit_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("G_T", "fake-token")
    monkeypatch.setattr(sys, "argv", ["blog-gen"])
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("""
github:
  repo: user/repo
  allowed_authors: [user]
site:
  title: T
  url: https://example.com/
  author: A
about:
  issue_number: 1
security:
  token_env: G_T
""")

    # Success -> no exit
    with patch("github_blog.cli.BlogGenerator") as mock_cls:
        mock_cls.return_value.generate.return_value = BuildResult(success=True)
        from github_blog.cli import run_cli

        run_cli()
        mock_cls.return_value.generate.assert_called_once()

    # Failure -> exit(1)
    with patch("github_blog.cli.BlogGenerator") as mock_cls:
        mock_cls.return_value.generate.return_value = BuildResult(
            success=False,
            diagnostics=(Diagnostic(severity="error", code="FAIL", message="boom"),),
        )
        from github_blog.cli import run_cli

        with pytest.raises(SystemExit) as exc:
            run_cli()
        assert exc.value.code == 1
