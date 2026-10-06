"""Delivery: how a release reaches PyPI."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_ROOT = Path(__file__).parent.parent.absolute()


def _step(steps: list[dict], name: str) -> dict:
    return next(step for step in steps if step.get("name") == name)


def test_release_publishes_the_tagged_version_without_a_stored_token() -> None:
    release = yaml.safe_load((_ROOT / ".github/workflows/release.yml").read_text())
    # PyYAML's YAML 1.1 loader reads the unquoted Actions `on` key as True.
    assert release[True] == {"push": {"tags": ["v*"]}}
    assert release["permissions"] == {}
    build, publish = release["jobs"]["build"], release["jobs"]["publish"]
    pinned = re.compile(r"[\w-]+/[\w-]+@[0-9a-f]{40}")
    for step in (*build["steps"], *publish["steps"]):
        assert "uses" not in step or pinned.fullmatch(step["uses"])
    # Only the job that runs no project code can ask PyPI for credentials.
    assert build["permissions"] == {"contents": "read"}
    assert publish["permissions"] == {"id-token": "write"}
    assert publish["needs"] == "build" and publish["environment"]["name"] == "pypi"
    assert not any("checkout" in step.get("uses", "") for step in publish["steps"])
    assert (
        'if [ "$TAG" != "v$version" ]'
        in _step(build["steps"], "Check that the tag is the package version")["run"]
    )
    text = (_ROOT / ".github/workflows/release.yml").read_text()
    assert "secrets." not in text and "password" not in text
