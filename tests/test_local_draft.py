from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from escaping.local_draft import prepare_local_draft
from escaping.utils.frontmatter import parse_front_matter, parse_yaml_envelope


@pytest.mark.parametrize("ending", ["\n", "\r\n", "\r"])
@pytest.mark.parametrize(
    "kind,metadata,labels",
    [
        ("blog", "", ["type:blog"]),
        ("idea", "tags: [notes]\n", ["type:idea", "tag:notes"]),
        (
            "about",
            'description: About me.\ncreated_date: "2020-02-29"\n',
            ["type:about"],
        ),
        ("blog", "slug: chosen\n", ["type:blog"]),
    ],
)
def test_draft_payload_preserves_body_and_only_authored_metadata(
    kind: str, metadata: str, labels: list[str], ending: str
) -> None:
    body = "---\n\n# 中文🙂\n\n![Picture](https://example.org/a.png)\n\n```yaml\ntitle: literal\n```\n  "
    body = body.replace("\n", ending)
    raw = (f"---\ntitle: Draft\ntype: {kind}\n{metadata}---\n").replace(
        "\n", ending
    ) + body
    payload, diagnostics = prepare_local_draft(raw)
    assert not diagnostics and payload is not None
    assert payload["title"] == "Draft" and payload["labels"] == labels
    envelope = parse_yaml_envelope(payload["body"])
    assert envelope is not None and envelope.body.encode() == body.encode()
    issue_metadata = metadata.replace("tags: [notes]\n", "")
    assert (
        envelope.fields == parse_front_matter(f"---\n{issue_metadata}---\nBody").fields
    )
    assert not {"title", "type", "tags"} & envelope.fields.keys()
    assert "published" not in payload["labels"]


@pytest.mark.parametrize(
    "fields,body,code",
    [
        ("type: blog", "Body", "TITLE_INVALID"),
        ("title: null\ntype: blog", "Body", "TITLE_INVALID"),
        ("title: 42\ntype: blog", "Body", "TITLE_INVALID"),
        ('title: " "\ntype: blog', "Body", "TITLE_EMPTY"),
        ("title: Draft", "Body", "TYPE_INVALID"),
        ("title: Draft\ntype: BLOG", "Body", "TYPE_INVALID"),
        ("title: Draft\ntype: [blog]", "Body", "TYPE_INVALID"),
        ("title: Draft\ntype: blog", " \r\n\t", "BODY_EMPTY"),
        ("title: Draft\ntype: blog\ntags: null", "Body", "TAGS_INVALID"),
        ("title: Draft\ntype: blog\ntags: notes", "Body", "TAGS_INVALID"),
        ("title: Draft\ntype: blog\ntags: [42]", "Body", "TAGS_INVALID"),
        ("title: Draft\ntype: blog\ntags: [notes, notes]", "Body", "TAG_DUPLICATE"),
        ("title: Draft\ntype: idea\ntags: [Notes]", "Body", "TAG_INVALID"),
        ("title: Draft\ntype: blog\ntags: ['tag:notes']", "Body", "TAG_INVALID"),
        ("title: Draft\ntype: about\ntags: []", "Body", "ABOUT_TAG_FORBIDDEN"),
        ("title: Draft\ntype: idea\nslug: null", "Body", "SLUG_FORBIDDEN"),
        ("title: Draft\ntype: blog\nslug: page", "Body", "SLUG_RESERVED"),
    ],
)
def test_local_identity_and_tag_rules_reject_without_a_payload(
    fields: str, body: str, code: str
) -> None:
    payload, diagnostics = prepare_local_draft(f"---\n{fields}\n---\n{body}")
    assert payload is None and code in {d.code for d in diagnostics}
    assert all(d.issue_number is None and d.field for d in diagnostics)


@pytest.mark.parametrize(
    "raw,code",
    [
        ("# Not an upload-ready Local Draft", "FRONT_MATTER_REQUIRED"),
        ("---\ntitle: Draft", "FRONT_MATTER_UNCLOSED"),
        ("---\ntitle: First\ntitle: Second\n---\nBody", "FRONT_MATTER_DUPLICATE_KEY"),
        ("---\nnull\n---\nBody", "FRONT_MATTER_NOT_MAPPING"),
        ("---\ntitle: !custom value\n---\nBody", "FRONT_MATTER_INVALID_YAML"),
        (
            "---\ntitle: Draft\ntype: blog\npublished: true\n---\nBody",
            "FRONT_MATTER_UNKNOWN_FIELD",
        ),
        (
            "---\ntitle: Draft\ntype: blog\n42: value\n---\nBody",
            "FRONT_MATTER_UNKNOWN_FIELD",
        ),
    ],
)
def test_local_envelope_uses_the_strict_parser(raw: str, code: str) -> None:
    payload, diagnostics = prepare_local_draft(raw)
    assert payload is None and code in {d.code for d in diagnostics}


def test_metadata_and_body_safety_share_compiler_rules_without_rewriting() -> None:
    raw = "---\ntitle: Draft\ntype: blog\ndescription: null\ncreated_date: !!str 2020-02-29\n---\nBody"
    payload, diagnostics = prepare_local_draft(raw)
    assert payload is None
    assert {d.code for d in diagnostics} == {
        "DESCRIPTION_INVALID",
        "CREATED_DATE_INVALID",
    }
    prefix = "---\ntitle: Draft\ntype: blog\n---\n"
    bad, errors = prepare_local_draft(prefix + "Use <button>.\n\nTail.")
    assert bad is None and {d.code for d in errors} == {"SANITIZER_FAILED"}
    body = 'Use `<button>`.\n\n<img src="https://example.org/a.png" onerror="bad()">\n\nTail.\n'
    good, errors = prepare_local_draft(prefix + body)
    assert not errors and good is not None
    envelope = parse_yaml_envelope(good["body"])
    assert envelope is not None and envelope.body == body


def test_module_is_read_only_without_gh_credentials_or_source_cwd(
    tmp_path: Path,
) -> None:
    # Source-module tracer, NOT the separately owned installed-wheel tracer.
    trap = tmp_path / "gh"
    trap.write_text("#!/bin/sh\necho unexpected-gh >> gh-called\nexit 99\n")
    trap.chmod(0o755)
    draft = tmp_path / "draft.md"
    raw = b"---\r\ntitle: Draft\r\ntype: blog\r\n---\r\n\r\nBody.\r\n"
    draft.write_bytes(raw)
    env = {
        **os.environ,
        "PATH": str(tmp_path),
        "HOME": str(tmp_path),
        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "GH_TOKEN": "",
        "GITHUB_TOKEN": "",
    }
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    for content, expected in ((raw, 0), (b"not a draft", 1), (b"\xff", 1)):
        draft.write_bytes(content)
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "escaping.local_draft", str(draft)],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == expected, result.stderr
        output = json.loads(result.stdout)
        assert (output["issue"] is not None) == (expected == 0)
        if expected == 0:
            assert output["diagnostics"] == []
            assert output["issue"]["body"].endswith("\r\nBody.\r\n")
        else:
            assert output["diagnostics"]
        assert draft.read_bytes() == content
        assert {p.name for p in tmp_path.iterdir()} == set(before)
    assert trap.read_bytes() == before["gh"]
