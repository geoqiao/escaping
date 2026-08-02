"""Strict configuration tests for the config contract.

Covers extra='forbid' at every level, repo format, allowed_authors
semantics, canonical HTTPS origin, token_env identifier validation,
page_size/about issue_number positivity, path child-name safety,
project/theme_lock validation, and settings loading.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

if TYPE_CHECKING:
    from github_blog.config import Settings

_BASE_YAML = """\
github:
  repo: geoqiao/geoqiao.github.io
  allowed_authors: [geoqiao]
site:
  title: Test Blog
  url: https://example.com
  author: Test Author
profile:
  avatar: https://github.com/geoqiao.png
  bio: Test bio
  links:
    - name: GitHub
      url: https://github.com/geoqiao
about:
  issue_number: 42
security:
  token_env: G_T
"""


def _load(yaml: str, tmp_path: Path) -> Settings:
    from github_blog.config import Settings

    p = tmp_path / "config.yaml"
    p.write_text(yaml)
    return Settings.load_from_yaml(p)


def _inject(base: str, marker: str, extra: str) -> str:
    """Insert *extra* after the first line containing *marker*."""
    i = base.index(marker)
    j = base.index("\n", i) + 1
    return base[:j] + extra + base[j:]


# ---------------------------------------------------------------------------
# extra='forbid' at every nested level
# ---------------------------------------------------------------------------

_UNKNOWN_FIELD_CASES = [
    (_BASE_YAML + "unknown_top: bad\n", "unknown_top"),
    (_inject(_BASE_YAML, "  allowed_authors:", "  gh_x: 1\n"), "gh_x"),
    (_inject(_BASE_YAML, "  author: Test Author", "  site_x: 1\n"), "site_x"),
    (_inject(_BASE_YAML, "  bio: Test bio", "  prof_x: 1\n"), "prof_x"),
    (_inject(_BASE_YAML, "  issue_number: 42", "  about_x: 1\n"), "about_x"),
    (_inject(_BASE_YAML, "  token_env: G_T", "  sec_x: 1\n"), "sec_x"),
    (_BASE_YAML + "paths:\n  output: out\n  paths_x: 1\n", "paths_x"),
    (_BASE_YAML + "comments:\n  provider: utterances\n  cmt_x: 1\n", "cmt_x"),
    (_BASE_YAML + "seo:\n  enable_sitemap: true\n  seo_x: 1\n", "seo_x"),
    (_BASE_YAML + "branding:\n  show_powered_by: true\n  br_x: 1\n", "br_x"),
    (
        _inject(
            _BASE_YAML,
            "  author: Test Author",
            "  navigation:\n    items: []\n    nav_x: 1\n",
        ),
        "nav_x",
    ),
    (
        _inject(
            _BASE_YAML,
            "  author: Test Author",
            "  navigation:\n    items:\n      - name: B\n        url: /b/\n        link_x: 1\n",
        ),
        "link_x",
    ),
    (
        _BASE_YAML
        + "projects:\n  - slug: p\n    title: P\n    repository: r\n    summary: s\n    proj_x: 1\n",
        "proj_x",
    ),
    (
        _BASE_YAML
        + "projects:\n  - slug: p\n    title: P\n    repository: r\n    summary: s\n"
        "    fallback_metadata:\n      stars: 1\n      meta_x: 1\n",
        "meta_x",
    ),
    (
        _BASE_YAML
        + "theme_lock:\n  repository: o/t\n  commit: "
        + "a" * 40
        + "\n  api_version: '1'\n  tl_x: 1\n",
        "tl_x",
    ),
    (
        _inject(
            _BASE_YAML, "      url: https://github.com/geoqiao", "      plink_x: 1\n"
        ),
        "plink_x",
    ),
]


@pytest.mark.parametrize(
    "yaml, match",
    _UNKNOWN_FIELD_CASES,
    ids=[c[1] for c in _UNKNOWN_FIELD_CASES],
)
def test_strict_unknown_fields_rejected(tmp_path: Path, yaml: str, match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        _load(yaml, tmp_path)


# ---------------------------------------------------------------------------
# GithubConfig
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "repo, ok",
    [
        ("geoqiao/blog", True),
        ("invalid-no-slash", False),
        ("/repo", False),
        ("user/", False),
        ("user/repo/extra", False),
        (" /repo", False),
        ("user/ ", False),
    ],
    ids=[
        "valid",
        "no-slash",
        "empty-owner",
        "empty-repo",
        "multi-slash",
        "ws-owner",
        "ws-repo",
    ],
)
def test_repo_format_validation(repo: str, ok: bool) -> None:
    from github_blog.config import GithubConfig

    if ok:
        cfg = GithubConfig(repo=repo, allowed_authors=["user"])
        assert cfg.repo == repo
    else:
        with pytest.raises(ValidationError):
            GithubConfig(repo=repo, allowed_authors=["user"])


def test_username_derived_from_repo() -> None:
    from github_blog.config import GithubConfig

    assert (
        GithubConfig(repo="geoqiao/blog", allowed_authors=["geoqiao"]).username
        == "geoqiao"
    )


@pytest.mark.parametrize(
    "yaml, match",
    [
        ("github:\n  repo: u/r\n", "allowed_authors"),
        ("github:\n  repo: u/r\n  allowed_authors: []\n", "allowed_authors"),
        (_BASE_YAML.replace("[geoqiao]", "[geoqiao, '']"), "blank"),
        (_BASE_YAML.replace("[geoqiao]", "[geoqiao, '   ']"), "blank"),
        (_BASE_YAML.replace("[geoqiao]", "[geoqiao, geoqiao]"), "duplicate"),
        (_BASE_YAML.replace("[geoqiao]", "[geoqiao, Geoqiao]"), "duplicate"),
    ],
    ids=["missing", "empty", "blank", "whitespace", "dup", "dup-ci"],
)
def test_allowed_authors_validation(tmp_path: Path, yaml: str, match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        _load(yaml, tmp_path)


def test_allowed_authors_accepts_distinct(tmp_path: Path) -> None:
    s = _load(_BASE_YAML.replace("[geoqiao]", "[geoqiao, alice]"), tmp_path)
    assert s.github.allowed_authors == ["geoqiao", "alice"]


# ---------------------------------------------------------------------------
# Canonical HTTPS origin
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, ok, match",
    [
        ("https://example.com", True, ""),
        ("https://example.com/", True, ""),
        ("http://example.com/", False, "HTTPS"),
        ("https://user:pass@example.com/", False, "userinfo"),
        ("https://example.com/blog", False, "root path"),
        ("https://example.com/?q=1", False, "query"),
        ("https://example.com/#frag", False, "fragment"),
        ("https://example.com/;foo", False, "path parameter"),
    ],
    ids=[
        "no-slash",
        "root-slash",
        "http",
        "userinfo",
        "path",
        "query",
        "fragment",
        "params",
    ],
)
def test_canonical_origin_validation(
    tmp_path: Path, url: str, ok: bool, match: str
) -> None:
    yaml = _BASE_YAML.replace("https://example.com", url)
    if ok:
        s = _load(yaml, tmp_path)
        assert s.site.url.scheme == "https"
    else:
        with pytest.raises(ValidationError, match=match):
            _load(yaml, tmp_path)


# ---------------------------------------------------------------------------
# Site, profile, about, paths defaults
# ---------------------------------------------------------------------------


def test_site_defaults(tmp_path: Path) -> None:
    from pydantic import HttpUrl

    from github_blog.config import SiteConfig

    cfg = SiteConfig(title="T", url=HttpUrl("https://x.com"), author="A")
    assert cfg.description == ""
    assert cfg.language == "en"
    assert cfg.navigation.items == []


def test_profile_fields(tmp_path: Path) -> None:
    from github_blog.config import SiteProfileConfig

    s = _load(_BASE_YAML, tmp_path)
    assert s.profile.avatar == "https://github.com/geoqiao.png"
    assert s.profile.bio == "Test bio"
    assert len(s.profile.links) == 1
    empty = SiteProfileConfig()
    assert empty.avatar == "" and empty.links == []


@pytest.mark.parametrize(
    "n, ok",
    [(1, True), (0, False), (-1, False)],
    ids=["positive", "zero", "negative"],
)
def test_about_issue_number_validation(n: int, ok: bool) -> None:
    from github_blog.config import AboutConfig

    if ok:
        assert AboutConfig(issue_number=n).issue_number == n
    else:
        with pytest.raises(ValidationError):
            AboutConfig(issue_number=n)


@pytest.mark.parametrize(
    "size, ok",
    [(10, True), (20, True), (0, False), (-5, False)],
    ids=["default", "custom", "zero", "negative"],
)
def test_page_size_validation(size: int, ok: bool) -> None:
    from github_blog.config import PathsConfig

    if ok:
        assert PathsConfig(page_size=size).page_size == size
    else:
        with pytest.raises(ValidationError):
            PathsConfig(page_size=size)


def test_paths_defaults_and_theme_path() -> None:
    from github_blog.config import PathsConfig

    cfg = PathsConfig()
    assert cfg.output == "output"
    assert cfg.theme == "Escape1"
    assert cfg.page_size == 10
    assert cfg.theme_path == Path("templates/Escape1")


@pytest.mark.parametrize(
    "field, bad_value",
    [
        ("theme", "../escape"),
        ("blog", "/abs/path"),
        ("tag", "a/b"),
        ("page", ".."),
        ("rss", "."),
        ("about", ""),
    ],
    ids=["theme", "blog", "tag", "page", "rss", "about"],
)
def test_paths_child_name_rejection(field: str, bad_value: str) -> None:
    """PathsConfig child-path fields reject escapes, separators, and traversal."""
    from github_blog.config import PathsConfig

    with pytest.raises(ValidationError, match="must not"):
        PathsConfig.model_validate({field: bad_value})


def test_comments_defaults(tmp_path: Path) -> None:
    from github_blog.config import CommentsConfig

    cfg = CommentsConfig()
    assert cfg.provider == "utterances"
    assert cfg.repo == ""
    assert cfg.theme == "github-light"
    assert cfg.theme_mode == "auto"


# ---------------------------------------------------------------------------
# SecurityConfig - dynamic token env
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, ok, match",
    [
        ("G_T", True, ""),
        ("_TOKEN", True, ""),
        ("MY_TOKEN_123", True, ""),
        ("", False, "blank"),
        ("   ", False, "blank"),
        ("1ABC", False, "identifier"),
        ("G-T", False, "identifier"),
        ("TOKEN!", False, "identifier"),
    ],
    ids=["valid", "underscore", "alnum", "empty", "ws", "digit", "hyphen", "special"],
)
def test_token_env_validation(value: str, ok: bool, match: str) -> None:
    from github_blog.config import SecurityConfig

    if ok:
        assert SecurityConfig(token_env=value).token_env == value
    else:
        with pytest.raises(ValidationError, match=match):
            SecurityConfig(token_env=value)


def test_no_hardcoded_token_constant() -> None:
    import github_blog.config as mod

    assert not hasattr(mod, "TOKEN_ENV_VAR")


def test_token_env_required() -> None:
    """token_env is required - omitting it must raise ValidationError."""
    from github_blog.config import SecurityConfig

    with pytest.raises(ValidationError):
        SecurityConfig.model_validate({})


# ---------------------------------------------------------------------------
# Project catalog & theme lock
# ---------------------------------------------------------------------------


def test_project_catalog_entry() -> None:
    from github_blog.config import ProjectCatalogEntry, ProjectFallbackMetadata

    e = ProjectCatalogEntry(slug="p", title="P", repository="r", summary="s")
    assert e.featured is False and e.order == 0
    e2 = ProjectCatalogEntry(
        slug="p",
        title="P",
        repository="r",
        summary="s",
        featured=True,
        order=2,
        fallback_metadata=ProjectFallbackMetadata(
            stars=100, forks=10, language="Python"
        ),
    )
    assert e2.fallback_metadata is not None
    assert e2.fallback_metadata.stars == 100
    with pytest.raises(ValidationError):
        ProjectFallbackMetadata(stars=-1)
    with pytest.raises(ValidationError):
        ProjectFallbackMetadata(forks=-1)


@pytest.mark.parametrize(
    "commit, ok, match",
    [("a" * 40, True, ""), ("abc123", False, "40-character"), ("g" * 40, False, "")],
    ids=["valid", "short", "non-hex"],
)
def test_theme_lock_commit_validation(commit: str, ok: bool, match: str) -> None:
    from github_blog.config import ThemeLockConfig

    if ok:
        assert (
            ThemeLockConfig(repository="r", commit=commit, api_version="1").commit
            == commit
        )
    else:
        with pytest.raises(ValidationError, match=match or "commit"):
            ThemeLockConfig(repository="r", commit=commit, api_version="1")


# ---------------------------------------------------------------------------
# Settings integration
# ---------------------------------------------------------------------------


def test_settings_load_from_yaml(tmp_path: Path) -> None:
    s = _load(_BASE_YAML, tmp_path)
    assert s.site.title == "Test Blog"
    assert s.github.repo == "geoqiao/geoqiao.github.io"
    assert s.about.issue_number == 42
    assert s.security.token_env == "G_T"  # noqa: S105
    assert s.projects == []
    assert s.theme_lock is None


def test_comments_repo_fallback(tmp_path: Path) -> None:
    s = _load(_BASE_YAML, tmp_path)
    assert s.comments.repo == ""
    assert (s.comments.repo or s.github.repo) == "geoqiao/geoqiao.github.io"
