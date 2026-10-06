"""Content Export: ``escpe export`` writes published Issues as Markdown files.

Selection and content rules belong to ``test_content_compiler.py``; these
tests own the exported files and the export directory.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from escaping.cli import main
from escaping.output_staging import OUTPUT_MARKER

_CONFIG = """\
github:
  repo: alice/site
  allowed_authors: [alice]
site:
  title: Site
  author: Alice
  url: https://example.com/
  description: A site.
profile:
  avatar: ""
  bio: A bio.
"""


def _issue(number: int, title: str, body: str, *labels: str) -> dict[str, object]:
    return {
        "number": number,
        "title": title,
        "body": body,
        "user": {"login": "alice"},
        "labels": [{"name": name} for name in ("published", *labels)],
        "created_at": f"2026-01-0{number}T08:00:00+08:00",
        "updated_at": f"2026-02-0{number}T00:00:00Z",
        "pull_request": None,
    }


_POST = _issue(
    1,
    "Title: with a colon",
    "---\r\nslug: first-post\r\ndescription: A summary.\r\n"
    'created_date: "2025-12-31"\r\n---\r\n\r\n## Heading\r\n\r\n'
    "<details>kept as written</details>\r\n\r\n---\r\n\r\nAfter a rule.",
    "type:blog",
    "tag:Daily Life",
)
_PLAIN = _issue(2, "Plain", "No front matter.", "type:blog")
_IDEA = _issue(3, "An idea", "A thought.", "type:idea", "tag:Notes")
_ABOUT = _issue(4, "About me", "Hello.", "type:about")
_BAD = _issue(5, "Bad", "Body.", "type:blog", "tag:C++")


@pytest.fixture
def site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "site"
    directory.mkdir()
    (directory / "config.yaml").write_text(_CONFIG, encoding="utf-8")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    return directory


def _export(site: Path, issues: list[dict[str, object]], *extra: str) -> int:
    path = site.parent / "issues.json"
    path.write_text(json.dumps(issues), encoding="utf-8")
    config = str(site / "config.yaml")
    return main(["export", "--config", config, "--issues-json", str(path), *extra])


def _read(path: Path) -> tuple[dict[str, object], str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    head, body = text[4:].split("\n---\n", 1)
    return yaml.safe_load(head), body


def test_export_writes_each_published_issue_and_a_manifest(site: Path) -> None:
    assert _export(site, [_POST, _PLAIN, _IDEA, _ABOUT]) == 0

    content = site / "build/content"
    assert (content / OUTPUT_MARKER).is_file()
    assert not (site / "output").exists()  # nothing is rendered

    meta, body = _read(content / "blog/first-post.md")
    assert meta == {
        "issue_number": 1,
        "type": "blog",
        "title": "Title: with a colon",
        "slug": "first-post",
        "description": "A summary.",
        "created_date": "2025-12-31",
        "published_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-02-01T00:00:00Z",
        "tags": [{"name": "Daily Life", "key": "daily-life"}],
    }
    # The Markdown is the author's: no envelope, no HTML rendering, LF endings.
    assert body == (
        "\n## Heading\n\n<details>kept as written</details>\n\n---\n\nAfter a rule.\n"
    )

    # Without front matter the contract's defaults are written out.
    meta, body = _read(content / "blog/2.md")
    assert (meta["slug"], meta["description"], meta["created_date"]) == (
        "2",
        "No front matter.",
        "2026-01-02",
    )
    assert body == "\nNo front matter.\n"

    meta, _ = _read(content / "ideas/3.md")
    assert meta["type"] == "idea" and "slug" not in meta
    assert meta["tags"] == [{"name": "Notes", "key": "notes"}]
    meta, _ = _read(content / "about.md")
    assert meta == {
        "issue_number": 4,
        "type": "about",
        "title": "About me",
        "description": "Hello.",
    }

    assert json.loads((content / "manifest.json").read_text(encoding="utf-8")) == {
        "export_version": 1,
        "repository": "alice/site",
        "blog": [
            {"issue_number": 2, "slug": "2", "path": "blog/2.md"},
            {"issue_number": 1, "slug": "first-post", "path": "blog/first-post.md"},
        ],
        "ideas": [{"issue_number": 3, "path": "ideas/3.md"}],
        "about": {"issue_number": 4, "path": "about.md"},
        "skipped_issues": [],
    }


def test_a_skipped_issue_is_left_out_and_reported(
    site: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _export(site, [_PLAIN, _BAD]) == 2

    content = site / "build/content"
    assert sorted(p.name for p in (content / "blog").iterdir()) == ["2.md"]
    manifest = json.loads((content / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["skipped_issues"] == [5] and manifest["about"] is None
    err = capsys.readouterr().err
    assert "error: Issue #5: Tag 'C++' must use letters" in err
    assert err.rstrip().endswith(
        "Exported build/content/. Skipped Issues #5; fix the errors above."
    )

    # The next export replaces the directory: a withdrawn Issue leaves no file.
    assert _export(site, [_POST]) == 0
    assert sorted(p.name for p in (content / "blog").iterdir()) == ["first-post.md"]


@pytest.mark.parametrize(
    ("output", "prepare", "message"),
    [
        ("build/mine", "build/mine/notes.md", "contains files escaping did not create"),
        ("content", None, "--output must start with an allowed folder"),
        ("output/content", None, "--output and paths.output overlap"),
    ],
)
def test_export_refuses_an_unsafe_directory(
    site: Path,
    capsys: pytest.CaptureFixture[str],
    output: str,
    prepare: str | None,
    message: str,
) -> None:
    if prepare:
        (site / prepare).parent.mkdir(parents=True)
        (site / prepare).write_text("mine", encoding="utf-8")

    assert _export(site, [_PLAIN], "--output", output) == 1

    assert message in capsys.readouterr().err
    if prepare:
        assert (site / prepare).read_text(encoding="utf-8") == "mine"
    assert not (site / output / "manifest.json").exists()
