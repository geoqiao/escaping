"""Tests for strict YAML front-matter envelope parsing and validation.

The Issue Content Contract v1 governs the front matter envelope: first-line
``---`` delimiter, closing ``---`` delimiter, YAML mapping, safe loader,
custom-tag rejection, duplicate-key rejection, 16 KiB UTF-8 limit, unknown
field rejection, and body extraction.
"""

from __future__ import annotations

import pytest

from github_blog.utils.frontmatter import FrontMatterError, parse_front_matter


class TestEnvelopeValidation:
    """Front matter envelope structure rules."""

    def test_valid_front_matter_parsed(self) -> None:
        body = '---\nslug: my-post\ndescription: A post.\ncreated_date: "2026-01-15"\n---\n\nBody text.'
        result = parse_front_matter(body)
        assert result.fields["slug"] == "my-post"
        assert result.fields["description"] == "A post."
        assert result.fields["created_date"] == "2026-01-15"
        assert result.body == "Body text."

    def test_missing_front_matter_raises(self) -> None:
        with pytest.raises(FrontMatterError) as exc_info:
            parse_front_matter("No front matter here.")
        assert exc_info.value.code == "FRONT_MATTER_MISSING"

    def test_first_line_must_be_exactly_triple_dash(self) -> None:
        with pytest.raises(FrontMatterError) as exc_info:
            parse_front_matter("--- \nslug: x\n---\nbody")
        assert exc_info.value.code == "FRONT_MATTER_MISSING"

    def test_missing_closing_delimiter_raises(self) -> None:
        with pytest.raises(FrontMatterError) as exc_info:
            parse_front_matter("---\nslug: x\nbody without closing")
        assert exc_info.value.code == "FRONT_MATTER_UNCLOSED"

    def test_front_matter_must_be_mapping(self) -> None:
        with pytest.raises(FrontMatterError) as exc_info:
            parse_front_matter("---\n- item1\n- item2\n---\nbody")
        assert exc_info.value.code == "FRONT_MATTER_NOT_MAPPING"

    def test_empty_front_matter_is_valid_mapping(self) -> None:
        """An empty mapping is syntactically valid; field validation is downstream."""
        result = parse_front_matter("---\n---\nbody")
        assert result.fields == {}
        assert result.body == "body"

    def test_body_starts_after_closing_delimiter(self) -> None:
        body = "---\nslug: x\n---\nFirst line.\n\nSecond paragraph."
        result = parse_front_matter(body)
        assert result.body == "First line.\n\nSecond paragraph."

    def test_body_with_leading_newline_after_delimiter(self) -> None:
        body = "---\nslug: x\n---\n\nBody starts here."
        result = parse_front_matter(body)
        assert result.body == "Body starts here."


class TestUTF8SizeLimit:
    def test_front_matter_under_16kib_succeeds(self) -> None:
        desc = "x" * 8000
        body = f"---\ndescription: {desc}\n---\nbody"
        result = parse_front_matter(body)
        assert result.fields["description"] == desc

    def test_front_matter_over_16kib_raises(self) -> None:
        desc = "x" * 17000
        body = f"---\ndescription: {desc}\n---\nbody"
        with pytest.raises(FrontMatterError) as exc_info:
            parse_front_matter(body)
        assert exc_info.value.code == "FRONT_MATTER_TOO_LARGE"

    def test_raw_crlf_bytes_over_16kib_rejected(self) -> None:
        """Front matter whose raw CRLF bytes exceed 16 KiB must be rejected,
        even though the normalized (LF-only) content is under 16 KiB.

        Each CRLF line ending adds one extra byte (``\r``) compared to LF.
        With enough lines, the raw bytes exceed 16 KiB while the normalized
        content stays under the limit.
        """
        # Build front matter with many short block-scalar lines using CRLF.
        # "description: |" header + N lines of "  x".
        # Normalized bytes: 15 + 4*N  (header + "\n  x" * N)
        # Raw CRLF bytes:   15 + 5*N  (header + "\r\n  x" * N)
        # Need: 15 + 4*N < 16384  AND  15 + 5*N > 16384
        #   =>  N < 4092.25  AND  N > 3273.8
        # Choose N = 3300: normalized=13215 < 16384, raw=16515 > 16384.
        n = 3300
        lines = ["---", "description: |"] + ["  x"] * n + ["---", "Body."]
        body_crlf = "\r\n".join(lines)
        body_lf = "\n".join(lines)

        # CRLF version exceeds 16 KiB in raw bytes.
        with pytest.raises(FrontMatterError) as exc_info:
            parse_front_matter(body_crlf)
        assert exc_info.value.code == "FRONT_MATTER_TOO_LARGE"

        # LF version is under 16 KiB and should succeed.
        result = parse_front_matter(body_lf)
        assert "description" in result.fields

    def test_raw_crlf_envelope_still_supported_when_under_limit(self) -> None:
        """CRLF front matter under 16 KiB raw bytes must still parse correctly."""
        body = "---\r\nslug: my-post\r\ndescription: A post.\r\n---\r\n\r\nBody text."
        result = parse_front_matter(body)
        assert result.fields["slug"] == "my-post"
        assert result.fields["description"] == "A post."
        assert result.body == "Body text."


class TestCustomTagRejection:
    def test_custom_yaml_tag_rejected(self) -> None:
        body = "---\nslug: !custom value\n---\nbody"
        with pytest.raises(FrontMatterError) as exc_info:
            parse_front_matter(body)
        assert exc_info.value.code == "FRONT_MATTER_INVALID_YAML"


class TestDuplicateKeyRejection:
    def test_duplicate_keys_rejected(self) -> None:
        body = "---\nslug: first\nslug: second\n---\nbody"
        with pytest.raises(FrontMatterError) as exc_info:
            parse_front_matter(body)
        assert exc_info.value.code == "FRONT_MATTER_DUPLICATE_KEY"


class TestUnknownFieldRejection:
    def test_unknown_field_rejected(self) -> None:
        body = "---\nslug: x\nunknown_field: value\n---\nbody"
        with pytest.raises(FrontMatterError) as exc_info:
            parse_front_matter(body)
        assert exc_info.value.code == "FRONT_MATTER_UNKNOWN_FIELD"
        assert exc_info.value.field == "unknown_field"

    def test_forbidden_field_title_rejected(self) -> None:
        body = "---\ntitle: My Title\n---\nbody"
        with pytest.raises(FrontMatterError) as exc_info:
            parse_front_matter(body)
        assert exc_info.value.code == "FRONT_MATTER_UNKNOWN_FIELD"

    def test_forbidden_field_type_rejected(self) -> None:
        body = "---\ntype: blog\n---\nbody"
        with pytest.raises(FrontMatterError) as exc_info:
            parse_front_matter(body)
        assert exc_info.value.code == "FRONT_MATTER_UNKNOWN_FIELD"

    def test_allowed_fields_accepted(self) -> None:
        body = '---\nslug: x\ndescription: desc\ncreated_date: "2026-01-01"\n---\nbody'
        result = parse_front_matter(body)
        assert set(result.fields.keys()) == {"slug", "description", "created_date"}

    def test_collect_unknown_fields_returns_known_fields_and_body(self) -> None:
        """With collect_unknown_fields=True, unknown fields are collected
        instead of raising, and known fields + body are returned.
        """
        body = (
            "---\n"
            "slug: my-post\n"
            "description: A post.\n"
            'created_date: "2026-01-01"\n'
            "foo: bar\n"
            "---\n\n"
            "Body text."
        )
        result = parse_front_matter(body, collect_unknown_fields=True)
        assert result.fields["slug"] == "my-post"
        assert result.fields["description"] == "A post."
        assert result.fields["created_date"] == "2026-01-01"
        assert "foo" not in result.fields
        assert "foo" in result.unknown_fields
        assert result.body == "Body text."

    def test_collect_unknown_fields_default_still_raises(self) -> None:
        """Default behavior (collect_unknown_fields=False) still raises."""
        body = "---\nslug: x\nfoo: bar\n---\nbody"
        with pytest.raises(FrontMatterError) as exc_info:
            parse_front_matter(body)
        assert exc_info.value.code == "FRONT_MATTER_UNKNOWN_FIELD"

    def test_collect_unknown_fields_no_unknown_returns_empty(self) -> None:
        """With collect_unknown_fields=True and no unknown fields, unknown_fields is empty."""
        body = '---\nslug: x\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody'
        result = parse_front_matter(body, collect_unknown_fields=True)
        assert result.unknown_fields == []
        assert set(result.fields.keys()) == {"slug", "description", "created_date"}

    def test_collect_unknown_fields_multiple(self) -> None:
        """Multiple unknown fields are all collected."""
        body = (
            "---\n"
            "slug: x\n"
            "description: d\n"
            'created_date: "2026-01-01"\n'
            "foo: 1\n"
            "bar: 2\n"
            "---\nbody"
        )
        result = parse_front_matter(body, collect_unknown_fields=True)
        assert set(result.unknown_fields) == {"foo", "bar"}
        assert set(result.fields.keys()) == {"slug", "description", "created_date"}


class TestSafeLoader:
    def test_python_object_tag_rejected(self) -> None:
        body = "---\nslug: !!python/object/apply:os.system ['echo hacked']\n---\nbody"
        with pytest.raises(FrontMatterError) as exc_info:
            parse_front_matter(body)
        assert exc_info.value.code == "FRONT_MATTER_INVALID_YAML"


class TestLineEndingNormalization:
    """CRLF and CR line endings must be normalized to LF before parsing."""

    def test_crlf_line_endings_normalized(self) -> None:
        body = "---\r\nslug: my-post\r\ndescription: A post.\r\n---\r\n\r\nBody text."
        result = parse_front_matter(body)
        assert result.fields["slug"] == "my-post"
        assert result.body == "Body text."

    def test_cr_only_line_endings_normalized(self) -> None:
        body = "---\rslug: my-post\rdescription: A post.\r---\r\rBody text."
        result = parse_front_matter(body)
        assert result.fields["slug"] == "my-post"
        assert result.body == "Body text."

    def test_crlf_with_trailing_content_normalized(self) -> None:
        body = "---\r\nslug: x\r\ndescription: d\r\n---\r\n\r\nHello."
        result = parse_front_matter(body)
        assert result.fields["slug"] == "x"
        assert result.body == "Hello."

    def test_mixed_line_endings_normalized(self) -> None:
        body = "---\r\nslug: x\ndescription: d\r---\n\nBody."
        result = parse_front_matter(body)
        assert result.fields["slug"] == "x"
        assert result.body == "Body."


class TestComplexMappingKeys:
    """Complex/unhashable mapping keys must produce structured diagnostics."""

    def test_list_key_produces_diagnostic(self) -> None:
        body = "---\n? [a, b]\n: value\nslug: x\n---\nbody"
        with pytest.raises(FrontMatterError) as exc_info:
            parse_front_matter(body)
        assert exc_info.value.code in {
            "FRONT_MATTER_INVALID_YAML",
            "FRONT_MATTER_COMPLEX_KEY",
        }

    def test_dict_key_produces_diagnostic(self) -> None:
        body = "---\n? {a: 1}\n: value\nslug: x\n---\nbody"
        with pytest.raises(FrontMatterError) as exc_info:
            parse_front_matter(body)
        assert exc_info.value.code in {
            "FRONT_MATTER_INVALID_YAML",
            "FRONT_MATTER_COMPLEX_KEY",
        }

    def test_complex_key_does_not_crash(self) -> None:
        """Complex keys must not escape as an unhandled TypeError."""
        body = "---\n? [a, b]\n: value\n---\nbody"
        # Must raise FrontMatterError, not TypeError or any other exception.
        with pytest.raises(FrontMatterError):
            parse_front_matter(body)


class TestScalarStyleMetadata:
    """The parser must preserve YAML scalar style for top-level fields.

    PyYAML's ``SafeLoader`` discards scalar style information during
    construction (a single-quoted ``'2026-01-01'`` and a plain
    ``!!str 2026-01-01`` both become the Python ``str`` ``"2026-01-01'"``).
    The parser must capture the node-level style so the compiler can enforce
    quoting requirements without resorting to regex on the raw YAML text.
    """

    def test_single_quoted_created_date_style(self) -> None:
        body = "---\ncreated_date: '2026-01-01'\n---\nbody"
        result = parse_front_matter(body)
        assert result.scalar_styles.get("created_date") == "'"

    def test_double_quoted_created_date_style(self) -> None:
        body = '---\ncreated_date: "2026-01-01"\n---\nbody'
        result = parse_front_matter(body)
        assert result.scalar_styles.get("created_date") == '"'

    def test_plain_created_date_style(self) -> None:
        body = "---\ncreated_date: 2026-01-01\n---\nbody"
        result = parse_front_matter(body)
        assert result.scalar_styles.get("created_date") is None

    def test_explicit_str_tag_created_date_has_plain_style(self) -> None:
        """``!!str 2026-01-01`` is plain style even though the constructed
        value is a Python ``str``."""
        body = "---\ncreated_date: !!str 2026-01-01\n---\nbody"
        result = parse_front_matter(body)
        assert result.scalar_styles.get("created_date") is None

    def test_literal_block_created_date_style(self) -> None:
        body = "---\ncreated_date: |-\n  2026-01-01\n---\nbody"
        result = parse_front_matter(body)
        assert result.scalar_styles.get("created_date") == "|"

    def test_folded_block_created_date_style(self) -> None:
        body = "---\ncreated_date: >-\n  2026-01-01\n---\nbody"
        result = parse_front_matter(body)
        assert result.scalar_styles.get("created_date") == ">"

    def test_scalar_styles_include_all_known_fields(self) -> None:
        body = (
            "---\nslug: my-post\ndescription: A post.\n"
            "created_date: '2026-01-01'\n---\nbody"
        )
        result = parse_front_matter(body)
        assert result.scalar_styles.get("slug") is None
        assert result.scalar_styles.get("description") is None
        assert result.scalar_styles.get("created_date") == "'"

    def test_no_scalar_style_for_missing_field(self) -> None:
        body = "---\nslug: my-post\n---\nbody"
        result = parse_front_matter(body)
        assert "created_date" not in result.scalar_styles

    def test_scalar_styles_not_polluted_by_nested_keys(self) -> None:
        """A nested mapping key with the same name must not overwrite the
        top-level scalar style."""
        body = (
            "---\n"
            "created_date: '2026-01-01'\n"
            "extra:\n"
            "  created_date: 2026-01-01\n"
            "---\nbody"
        )
        result = parse_front_matter(body, collect_unknown_fields=True)
        assert result.scalar_styles.get("created_date") == "'"
