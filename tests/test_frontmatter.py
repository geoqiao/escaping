"""Strict YAML front-matter envelope parsing and validation tests.

Covers: envelope structure, 16 KiB UTF-8 limit (raw CRLF bytes), custom-tag
rejection, duplicate-key rejection, unknown-field rejection/collection,
line-ending normalization, complex mapping keys, and scalar style metadata
for created_date quoting enforcement.
"""

from __future__ import annotations

import pytest

from github_blog.utils.frontmatter import (
    FRONT_MATTER_MAX_BYTES,
    FrontMatterError,
    parse_front_matter,
)

# ---------------------------------------------------------------------------
# Envelope validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body, code",
    [
        (
            '---\nslug: my-post\ndescription: A post.\ncreated_date: "2026-01-15"\n---\n\nBody text.',
            None,
        ),
        ("No front matter here.", "FRONT_MATTER_MISSING"),
        ("--- \nslug: x\n---\nbody", "FRONT_MATTER_MISSING"),
        ("---\nslug: x\nbody without closing", "FRONT_MATTER_UNCLOSED"),
        ("---\n- item1\n- item2\n---\nbody", "FRONT_MATTER_NOT_MAPPING"),
        ("---\n---\nbody", None),  # empty mapping is valid
    ],
    ids=[
        "valid",
        "missing",
        "first-line-space",
        "unclosed",
        "not-mapping",
        "empty-mapping",
    ],
)
def test_envelope_validation(body: str, code: str | None) -> None:
    if code is None:
        result = parse_front_matter(body)
        if "slug" in body:
            assert result.fields["slug"] == "my-post"
            assert result.body == "Body text."
    else:
        with pytest.raises(FrontMatterError) as exc:
            parse_front_matter(body)
        assert exc.value.code == code


def test_body_extraction() -> None:
    result = parse_front_matter("---\nslug: x\n---\nFirst line.\n\nSecond paragraph.")
    assert result.body == "First line.\n\nSecond paragraph."
    result2 = parse_front_matter("---\nslug: x\n---\n\nBody starts here.")
    assert result2.body == "Body starts here."


# ---------------------------------------------------------------------------
# 16 KiB UTF-8 size limit (raw CRLF bytes)
# ---------------------------------------------------------------------------


def test_front_matter_over_16kib_raises() -> None:
    # Exactly 16 KiB is accepted (boundary)
    n = FRONT_MATTER_MAX_BYTES - len("description: ")
    body_boundary = f"---\ndescription: {'x' * n}\n---\nbody"
    result = parse_front_matter(body_boundary)
    assert "description" in result.fields

    # Over 16 KiB is rejected
    body = f"---\ndescription: {'x' * 17000}\n---\nbody"
    with pytest.raises(FrontMatterError) as exc:
        parse_front_matter(body)
    assert exc.value.code == "FRONT_MATTER_TOO_LARGE"


def test_raw_crlf_bytes_over_16kib_rejected() -> None:
    """Raw CRLF bytes exceeding 16 KiB must be rejected even though
    normalized (LF-only) content is under the limit."""
    n = 3300
    lines = ["---", "description: |"] + ["  x"] * n + ["---", "Body."]
    body_crlf = "\r\n".join(lines)
    body_lf = "\n".join(lines)
    with pytest.raises(FrontMatterError) as exc:
        parse_front_matter(body_crlf)
    assert exc.value.code == "FRONT_MATTER_TOO_LARGE"
    result = parse_front_matter(body_lf)
    assert "description" in result.fields


# ---------------------------------------------------------------------------
# Custom tag & duplicate key rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body, code",
    [
        ("---\nslug: !custom value\n---\nbody", "FRONT_MATTER_INVALID_YAML"),
        (
            "---\nslug: !!python/object/apply:os.system ['echo hacked']\n---\nbody",
            "FRONT_MATTER_INVALID_YAML",
        ),
        ("---\nslug: first\nslug: second\n---\nbody", "FRONT_MATTER_DUPLICATE_KEY"),
    ],
    ids=["custom-tag", "python-tag", "duplicate-key"],
)
def test_custom_tag_and_duplicate_key_rejected(body: str, code: str) -> None:
    with pytest.raises(FrontMatterError) as exc:
        parse_front_matter(body)
    assert exc.value.code == code


# ---------------------------------------------------------------------------
# Unknown field rejection / collection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body, code, field",
    [
        (
            "---\nslug: x\nunknown_field: value\n---\nbody",
            "FRONT_MATTER_UNKNOWN_FIELD",
            "unknown_field",
        ),
        ("---\ntitle: My Title\n---\nbody", "FRONT_MATTER_UNKNOWN_FIELD", "title"),
        ("---\ntype: blog\n---\nbody", "FRONT_MATTER_UNKNOWN_FIELD", "type"),
    ],
    ids=["unknown", "forbidden-title", "forbidden-type"],
)
def test_unknown_field_rejected(body: str, code: str, field: str) -> None:
    with pytest.raises(FrontMatterError) as exc:
        parse_front_matter(body)
    assert exc.value.code == code
    assert exc.value.field == field


def test_allowed_fields_accepted() -> None:
    body = '---\nslug: x\ndescription: desc\ncreated_date: "2026-01-01"\n---\nbody'
    result = parse_front_matter(body)
    assert set(result.fields.keys()) == {"slug", "description", "created_date"}


def test_collect_unknown_fields() -> None:
    body = (
        "---\nslug: my-post\ndescription: A post.\n"
        'created_date: "2026-01-01"\nfoo: bar\nbaz: 2\n---\n\nBody text.'
    )
    result = parse_front_matter(body, collect_unknown_fields=True)
    assert set(result.fields.keys()) == {"slug", "description", "created_date"}
    assert set(result.unknown_fields) == {"foo", "baz"}
    assert result.body == "Body text."
    # Default still raises
    with pytest.raises(FrontMatterError, match="Unknown field"):
        parse_front_matter("---\nslug: x\nfoo: bar\n---\nbody")


# ---------------------------------------------------------------------------
# Line-ending normalization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        "---\r\nslug: my-post\r\ndescription: A post.\r\n---\r\n\r\nBody text.",
        "---\rslug: my-post\rdescription: A post.\r---\r\rBody text.",
        "---\r\nslug: x\ndescription: d\r---\n\nBody.",
        "---\r\nslug: x\r\ndescription: d\r\n---\r\n\r\nHello.",
    ],
    ids=["crlf", "cr", "mixed", "crlf-trailing"],
)
def test_line_ending_normalization(body: str) -> None:
    result = parse_front_matter(body)
    assert result.fields["slug"] in ("my-post", "x")
    assert "Body" in result.body or "Hello" in result.body


# ---------------------------------------------------------------------------
# Complex mapping keys
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        "---\n? [a, b]\n: value\nslug: x\n---\nbody",
        "---\n? {a: 1}\n: value\nslug: x\n---\nbody",
        "---\n? [a, b]\n: value\n---\nbody",
    ],
    ids=["list-key", "dict-key", "list-key-no-slug"],
)
def test_complex_mapping_keys(body: str) -> None:
    with pytest.raises(FrontMatterError) as exc:
        parse_front_matter(body)
    assert exc.value.code in {"FRONT_MATTER_INVALID_YAML", "FRONT_MATTER_COMPLEX_KEY"}


# ---------------------------------------------------------------------------
# Scalar style metadata (for created_date quoting enforcement)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body, expected_style",
    [
        ("---\ncreated_date: '2026-01-01'\n---\nbody", "'"),
        ('---\ncreated_date: "2026-01-01"\n---\nbody', '"'),
        ("---\ncreated_date: 2026-01-01\n---\nbody", None),
        ("---\ncreated_date: !!str 2026-01-01\n---\nbody", None),
        ("---\ncreated_date: |-\n  2026-01-01\n---\nbody", "|"),
        ("---\ncreated_date: >-\n  2026-01-01\n---\nbody", ">"),
    ],
    ids=[
        "single-quoted",
        "double-quoted",
        "plain",
        "explicit-str",
        "literal-block",
        "folded-block",
    ],
)
def test_scalar_style_metadata(body: str, expected_style: str | None) -> None:
    result = parse_front_matter(body)
    assert result.scalar_styles.get("created_date") == expected_style


def test_scalar_style_not_polluted_by_nested_keys() -> None:
    body = (
        "---\ncreated_date: '2026-01-01'\nextra:\n  created_date: 2026-01-01\n---\nbody"
    )
    result = parse_front_matter(body, collect_unknown_fields=True)
    assert result.scalar_styles.get("created_date") == "'"


def test_no_scalar_style_for_missing_field() -> None:
    result = parse_front_matter("---\nslug: my-post\n---\nbody")
    assert "created_date" not in result.scalar_styles
