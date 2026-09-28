"""Themes from a GitHub repository, served here by a local stand-in for GitHub."""

from __future__ import annotations

import io
import shutil
import tarfile
import threading
from collections.abc import Iterator
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from escaping import remote_theme
from escaping.config import Settings
from escaping.remote_theme import DownloadError, RemoteTheme, download
from escaping.site_compiler import check_theme
from escaping.theme import ThemeError, ThemeLoader

_ROOT = Path(__file__).resolve().parents[1]
_COMMIT = "0123456789abcdef0123456789abcdef01234567"


def _archive(repo: str, ref: str, source: Path) -> bytes:
    """A tarball shaped like GitHub's: one top folder and the commit in a header."""
    buffer = io.BytesIO()
    with tarfile.open(
        fileobj=buffer,
        mode="w:gz",
        format=tarfile.PAX_FORMAT,
        pax_headers={"comment": _COMMIT},
    ) as tar:
        tar.add(source, arcname=f"{repo}-{ref}")
    return buffer.getvalue()


@pytest.fixture
def github(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Serve ``<return value>/<owner>/<repo>/<ref>/`` as that repository's archive."""
    repos = tmp_path / "repos"
    repos.mkdir()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            owner, repo, _, ref = self.path.strip("/").split("/")
            source = repos / owner / repo / ref
            if not source.is_dir():
                self.send_error(404)
                return
            body = _archive(repo, ref, source)
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    monkeypatch.setattr(
        remote_theme,
        "ARCHIVE_URL",
        f"http://127.0.0.1:{port}/{{owner}}/{{repo}}/tar.gz/{{ref}}",
    )
    try:
        yield repos
    finally:
        server.shutdown()
        server.server_close()


def _themes_repo(repos: Path, ref: str = "v1.0.0") -> Path:
    """alice/themes at ``ref``: two Themes in folders, and a README."""
    root = repos / "alice" / "themes" / ref
    shutil.copytree(_ROOT / "tests/fixtures/minimal_theme", root / "plain")
    shutil.copytree(_ROOT / "tests/fixtures/independent_theme", root / "full")
    (root / "README.md").write_text("Two Themes.\n", encoding="utf-8")
    return root


def test_one_theme_folder_is_unpacked_from_a_repository_of_themes(
    github: Path, tmp_path: Path
) -> None:
    _themes_repo(github)
    into = tmp_path / "downloads"
    into.mkdir()

    root = download(RemoteTheme.parse("github.com/alice/themes/plain@v1.0.0"), into)

    assert (root / "theme.yaml").is_file()
    assert root.name == "plain"
    # Nothing else from the repository is unpacked.
    assert [p.name for p in root.parent.iterdir()] == ["plain"]


@pytest.mark.parametrize(
    ("address", "problem"),
    [
        (
            "github.com/alice/missing/plain@v1.0.0",
            "GitHub has no public repository alice/missing with a tag, branch or "
            "commit v1.0.0",
        ),
        (
            "github.com/alice/themes/plain@v9",
            "GitHub has no public repository alice/themes",
        ),
        ("github.com/alice/themes/nothing@v1.0.0", "has no folder nothing at v1.0.0"),
    ],
)
def test_a_theme_that_is_not_there_names_what_is_missing(
    github: Path, tmp_path: Path, address: str, problem: str
) -> None:
    _themes_repo(github)

    with pytest.raises(DownloadError, match=problem):
        download(RemoteTheme.parse(address), tmp_path)


def test_a_symbolic_link_in_the_theme_folder_is_refused(
    github: Path, tmp_path: Path
) -> None:
    repo = _themes_repo(github)
    (repo / "plain" / "link.html").symlink_to(repo / "README.md")

    with pytest.raises(DownloadError, match=r"plain/link.html is a symbolic link"):
        download(RemoteTheme.parse("github.com/alice/themes/plain@v1.0.0"), tmp_path)


def test_a_site_theme_can_extend_a_github_theme_and_reuse_its_files(
    github: Path, tmp_path: Path
) -> None:
    _themes_repo(github)
    site = tmp_path / "site"
    (site / "theme").mkdir(parents=True)
    (site / "theme" / "theme.yaml").write_text(
        "api: 4\nextends: github.com/alice/themes/full@v1.0.0\n", encoding="utf-8"
    )
    (site / "theme" / "post.html").write_text(
        '{% extends "@full/post.html" %}', encoding="utf-8"
    )
    downloads = tmp_path / "downloads"
    downloads.mkdir()

    theme = ThemeLoader(site, partial(download, into=downloads)).load("./theme")

    assert [layer.name for layer in theme.layers] == [
        "./theme",
        "github.com/alice/themes/full@v1.0.0",
    ]
    assert theme.environment().get_template("post.html") is not None


def test_theme_check_downloads_the_theme_and_removes_it_afterwards(
    github: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _themes_repo(github)
    downloads: list[Path] = []
    real = remote_theme.download

    def spy(theme: RemoteTheme, into: Path) -> Path:
        downloads.append(into)
        return real(theme, into)

    monkeypatch.setattr("escaping.site_compiler.download", spy)
    settings = Settings.model_validate(
        {
            "github": {"repo": "alice/site", "allowed_authors": ["alice"]},
            "site": {
                "title": "Site",
                "author": "Alice",
                "url": "https://alice.github.io/notes/",
            },
            "theme": {"use": "github.com/alice/themes/plain@v1.0.0"},
            "pages": {"tags": False, "projects": False},
        }
    )

    result = check_theme(settings, config_root=tmp_path / "site")

    assert result.success, result.diagnostics
    assert len(downloads) == 1 and not downloads[0].exists()


def test_a_failed_download_stops_the_theme_check_with_the_address(
    github: Path, tmp_path: Path
) -> None:
    settings = Settings.model_validate(
        {
            "github": {"repo": "alice/site", "allowed_authors": ["alice"]},
            "site": {"title": "Site", "author": "Alice", "url": "https://a.example/"},
            "theme": {"use": "github.com/alice/themes/plain@v1.0.0"},
        }
    )

    result = check_theme(settings, config_root=tmp_path)

    assert not result.success
    assert [d.code for d in result.diagnostics] == ["THEME_INVALID"]
    assert result.diagnostics[0].message.startswith(
        "github.com/alice/themes/plain@v1.0.0: GitHub has no public repository"
    )


def test_loading_a_github_theme_without_a_way_to_download_is_a_program_error(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="needs fetch"):
        ThemeLoader(tmp_path).load("github.com/alice/themes/plain@v1.0.0")


def test_an_invalid_extends_address_names_the_theme(tmp_path: Path) -> None:
    (tmp_path / "theme").mkdir()
    (tmp_path / "theme" / "theme.yaml").write_text(
        "api: 4\nextends: github.com/alice/themes/full\n", encoding="utf-8"
    )

    with pytest.raises(ThemeError, match="add the version to use after @"):
        ThemeLoader(tmp_path, lambda theme: tmp_path).load("./theme")
