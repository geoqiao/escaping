"""Read-only Local Draft validation: python -m escaping.local_draft <path>.

Produces a creation payload, not an upload, publication approval or local state.
The GitHub Issue becomes authoritative only through a separately authorized tool.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import TypedDict, cast

import yaml

from .build_result import Diagnostic
from .content_validation import (
    CONTENT_TYPES,
    render_body,
    reserved_blog_slug,
    validate_authored_content,
)
from .utils.frontmatter import (
    ALLOWED_FIELDS,
    FrontMatterError,
    ParsedFrontMatter,
    parse_yaml_envelope,
)

_LOCAL_FIELDS = ALLOWED_FIELDS | {"title", "type", "tags"}


class IssueDraftPayload(TypedDict):
    title: str
    body: str
    labels: list[str]


def prepare_local_draft(
    raw: str,
) -> tuple[IssueDraftPayload | None, tuple[Diagnostic, ...]]:
    """Validate original YAML before serializing only supplied Issue metadata.

    No IssueSnapshot, number, clock, repository, credentials or filesystem writes.
    The separated Markdown suffix is preserved, not replaced by sanitized HTML.
    """
    try:
        parsed = parse_yaml_envelope(raw)
    except FrontMatterError as exc:
        return None, (Diagnostic("error", exc.code, exc.message, field=exc.field),)
    if parsed is None:
        return None, (
            Diagnostic(
                "error",
                "FRONT_MATTER_REQUIRED",
                "Local Draft requires a YAML envelope",
                field="body",
            ),
        )

    fields = parsed.fields
    errors = [
        Diagnostic(
            "error",
            "FRONT_MATTER_UNKNOWN_FIELD",
            f"Unknown Local Draft field: {key!r}",
            field=str(key),
        )
        for key in fields
        if not isinstance(key, str) or key not in _LOCAL_FIELDS
    ]
    title = fields.get("title")
    kind = fields.get("type")
    tags = fields.get("tags", [])
    if not isinstance(title, str):
        errors.append(
            Diagnostic(
                "error", "TITLE_INVALID", "title must be a scalar string", field="title"
            )
        )
    if not isinstance(kind, str) or kind not in CONTENT_TYPES:
        errors.append(
            Diagnostic(
                "error",
                "TYPE_INVALID",
                "type must be blog, idea or about",
                field="type",
            )
        )
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        errors.append(
            Diagnostic(
                "error",
                "TAGS_INVALID",
                "tags must be a list of string keys",
                field="tags",
            )
        )
    elif len(tags) != len(set(tags)):
        errors.append(
            Diagnostic(
                "error",
                "TAG_DUPLICATE",
                "tags must not contain duplicate keys",
                field="tags",
            )
        )
    if kind == "about" and "tags" in fields:
        errors.append(
            Diagnostic(
                "error",
                "ABOUT_TAG_FORBIDDEN",
                "About must not provide tags",
                field="tags",
            )
        )
    if errors:
        return None, tuple(errors)

    # The checks above prove these types; casts do not coerce authored values.
    title, kind, tags = cast(str, title), cast(str, kind), cast(list[str], tags)
    metadata = {key: value for key, value in fields.items() if key in ALLOWED_FIELDS}
    authored = ParsedFrontMatter(
        fields=metadata, body=parsed.body, scalar_styles=parsed.scalar_styles
    )
    errors.extend(validate_authored_content(title, kind, tags, authored))
    if (
        kind == "blog"
        and isinstance(slug := metadata.get("slug"), str)
        and (reserved := reserved_blog_slug(slug))
    ):
        errors.append(reserved)
    if errors:
        return None, tuple(errors)
    _, body_errors = render_body(parsed.body)
    if body_errors:
        return None, body_errors

    # Always frame metadata, including {}: a body beginning with --- must not
    # accidentally declare a second envelope. Never dump before date validation.
    # Preserve required date quoting even when YAML does not infer a timestamp.
    envelope = yaml.safe_dump(
        metadata, allow_unicode=True, sort_keys=False, default_style='"'
    )
    return {
        "title": title,
        "body": f"---\n{envelope}---\n" + parsed.body,
        "labels": [f"type:{kind}", *(f"tag:{tag}" for tag in tags)],
    }, ()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check one Local Draft without uploading or modifying it"
    )
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        raw = args.path.read_bytes().decode("utf-8")
    except OSError, UnicodeError:
        issue = None
        diagnostics = (
            Diagnostic(
                "error",
                "DRAFT_READ_FAILED",
                "Cannot read Local Draft as UTF-8",
                field="path",
            ),
        )
    else:
        issue, diagnostics = prepare_local_draft(raw)
    print(
        json.dumps(
            {"issue": issue, "diagnostics": [asdict(d) for d in diagnostics]},
            ensure_ascii=False,
        )
    )
    return 1 if diagnostics else 0


if __name__ == "__main__":
    raise SystemExit(main())
