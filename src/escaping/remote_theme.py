"""Themes in a public GitHub repository: ``github.com/OWNER/REPO[/FOLDER]@VERSION``.

VERSION is a tag, a branch or a commit. The repository at that version is
downloaded as one archive over HTTPS, without a token, and only FOLDER is
unpacked. One repository can hold many Themes, one per folder.
"""

from __future__ import annotations

import http.client
import io
import re
import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import structlog

logger = structlog.get_logger()

PREFIX = "github.com/"
#: Tests point this at a local server.
ARCHIVE_URL = "https://codeload.github.com/{owner}/{repo}/tar.gz/{ref}"
#: A larger archive, or a larger Theme folder, is refused.
MAX_BYTES = 50 * 1024 * 1024
_MB = MAX_BYTES // (1024 * 1024)
_TIMEOUT_SECONDS = 60

_ADDRESS = re.compile(
    r"github\.com/(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))"
    r"/(?P<repo>[A-Za-z0-9._-]+)(?P<folder>(?:/[A-Za-z0-9._-]+)*)"
    r"@(?P<ref>[A-Za-z0-9][A-Za-z0-9._-]*)"
)
_EXAMPLE = "github.com/alice/themes/paper@v1.0.0"


class DownloadError(Exception):
    """The Theme could not be downloaded or unpacked; the text says why."""


@dataclass(frozen=True)
class RemoteTheme:
    owner: str
    repo: str
    folder: str  # "" when the Theme is the whole repository
    ref: str

    @classmethod
    def parse(cls, value: str) -> RemoteTheme:
        """Raise ValueError with the fix when ``value`` is not an address."""
        match = _ADDRESS.fullmatch(value)
        if match is None:
            if "@" not in value:
                raise ValueError(f"add the version to use after @, such as {_EXAMPLE}")
            raise ValueError(
                f"write github.com/OWNER/REPOSITORY/FOLDER@VERSION, such as {_EXAMPLE}"
            )
        folder = match["folder"].removeprefix("/")
        names = [match["repo"], *(folder.split("/") if folder else [])]
        if any(name in {".", ".."} for name in names) or ".." in match["ref"]:
            raise ValueError("a folder or version cannot be . or contain ..")
        return cls(match["owner"], match["repo"], folder, match["ref"])

    def __str__(self) -> str:
        folder = f"/{self.folder}" if self.folder else ""
        return f"{PREFIX}{self.owner}/{self.repo}{folder}@{self.ref}"

    @property
    def short_name(self) -> str:
        """The folder name (or repository name), used as ``@name/`` in templates."""
        return PurePosixPath(self.folder).name if self.folder else self.repo


def download(theme: RemoteTheme, into: Path) -> Path:
    """Unpack ``theme`` into a new directory under ``into`` and return it."""
    url = ARCHIVE_URL.format(owner=theme.owner, repo=theme.repo, ref=theme.ref)
    # The URL is ARCHIVE_URL with checked names: https, never file: or others.
    request = urllib.request.Request(url, headers={"User-Agent": "escaping"})  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:  # noqa: S310
            data = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise DownloadError(
                f"GitHub has no public repository {theme.owner}/{theme.repo} "
                f"with a tag, branch or commit {theme.ref}"
            ) from None
        raise DownloadError(f"the download failed with HTTP {exc.code}") from None
    except (OSError, http.client.HTTPException) as exc:
        reason = getattr(exc, "reason", exc)
        raise DownloadError(f"the download failed: {reason}") from None
    if len(data) > MAX_BYTES:
        raise DownloadError(f"the repository archive is larger than {_MB} MB")
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            root = _unpack(archive, theme, Path(tempfile.mkdtemp(dir=into)))
            commit = archive.pax_headers.get("comment", "")
    except tarfile.TarError as exc:
        raise DownloadError(f"the archive could not be unpacked: {exc}") from None
    logger.info("theme_downloaded", theme=str(theme), commit=commit)
    return root


def _unpack(archive: tarfile.TarFile, theme: RemoteTheme, target: Path) -> Path:
    members = archive.getmembers()
    tops = {member.name.split("/", 1)[0] for member in members}
    if len(tops) != 1:
        raise DownloadError("the archive does not hold one repository folder")
    top = tops.pop()
    base = f"{top}/{theme.folder}" if theme.folder else top
    chosen = []
    for member in members:
        if member.name != base and not member.name.startswith(f"{base}/"):
            continue
        relative = member.name.removeprefix(f"{top}/")
        if member.issym() or member.islnk():
            raise DownloadError(
                f"{relative} is a symbolic link; a Theme must contain the file itself"
            )
        if member.isfile() or member.isdir():
            chosen.append(member)
    if sum(member.size for member in chosen) > MAX_BYTES:
        raise DownloadError(f"the Theme folder is larger than {_MB} MB")
    archive.extractall(target, members=chosen, filter="data")
    root = target / base
    if not root.is_dir():
        where = f"no folder {theme.folder}" if theme.folder else "no files"
        raise DownloadError(f"the repository has {where} at {theme.ref}")
    return root
