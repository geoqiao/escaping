from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent.absolute()


@pytest.fixture(scope="session")
def source_snapshot(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """This checkout as git would ship it: tracked and new files, pending edits.

    Ignored build output (``build/``, ``*.egg-info``) never leaks into
    packaging tests, and nothing is written back into the checkout.
    """
    git = shutil.which("git")
    assert git is not None
    names = subprocess.check_output(  # noqa: S603 - local file inventory
        [git, "-C", str(_ROOT), "ls-files", "-z", "-co", "--exclude-standard"],
        text=True,
    ).split("\0")
    snapshot = tmp_path_factory.mktemp("source") / "escaping"
    for name in names:
        if name and (_ROOT / name).is_file():
            (snapshot / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(_ROOT / name, snapshot / name)
    return snapshot
