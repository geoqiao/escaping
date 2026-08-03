"""Strict YAML front-matter envelope parser.

Implements the Issue Content Contract v1 front-matter envelope rules:
- First line MUST be exactly ``---``.
- Closing delimiter MUST be a line containing exactly ``---``.
- The front matter MUST be a YAML mapping.
- YAML MUST be parsed with a safe loader.
- Custom YAML tags MUST be rejected.
- Duplicate mapping keys MUST be rejected.
- Front matter MUST NOT exceed 16 KiB encoded as UTF-8.
- Unknown fields MUST be rejected (only ``slug``, ``description``,
  ``created_date`` are allowed).

The Markdown body (everything after the closing delimiter, with one leading
newline consumed) is returned separately so it can be passed to the Markdown
renderer without any front-matter contamination.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml
from yaml.constructor import ConstructorError

#: Maximum front-matter size in UTF-8 bytes (16 KiB).
FRONT_MATTER_MAX_BYTES: int = 16 * 1024

#: Allowed front-matter field names per the Issue Content Contract.
ALLOWED_FIELDS: frozenset[str] = frozenset({"slug", "description", "created_date"})

#: Pattern matching any line ending (CRLF, CR, or LF).
_LINE_ENDING_RE: re.Pattern[str] = re.compile(r"\r\n|\r|\n")


class FrontMatterError(Exception):
    """Raised when front-matter envelope validation fails.

    Attributes:
        code: Stable machine-readable error code.
        message: Human-readable description.
        field: Field name when the error is field-specific.
    """

    def __init__(
        self,
        code: str,
        message: str,
        field: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.field = field
        super().__init__(message)


@dataclass(frozen=True)
class ParsedFrontMatter:
    """Result of parsing front matter from an Issue body.

    Attributes:
        fields: Validated front-matter field values (only allowed keys).
        body: Markdown body after the closing delimiter.
        unknown_fields: Names of fields not in ``ALLOWED_FIELDS``, collected
            only when ``collect_unknown_fields=True`` is passed to
            :func:`parse_front_matter`.  Empty otherwise.
        scalar_styles: YAML node-level style for top-level scalar values,
            keyed by field name.  Values are the PyYAML scalar style
            indicator: ``'"'`` for double-quoted, ``"'"`` for
            single-quoted, ``'|'`` for literal block, ``'>'`` for folded
            block, and ``None`` for plain.  Non-scalar values are omitted.
            This lets the compiler enforce quoting requirements without
            regex-parsing the raw YAML text.
    """

    fields: dict[str, object] = field(default_factory=dict)
    body: str = ""
    unknown_fields: list[str] = field(default_factory=list)
    scalar_styles: dict[str, str | None] = field(default_factory=dict)


class _StrictYAMLLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys and captures
    top-level scalar style metadata.

    Custom YAML tags are already rejected by ``SafeLoader`` (it raises
    ``ConstructorError`` for any tag without a registered constructor).
    This subclass additionally detects duplicate keys before construction
    completes, and records the YAML scalar style of top-level mapping
    values so callers can enforce quoting requirements.
    """

    def __init__(self, stream: str) -> None:
        super().__init__(stream)
        #: Maps top-level field name -> PyYAML scalar style indicator
        #: (``'"'``, ``"'"``, ``'|'``, ``'>'``, or ``None`` for plain).
        #: Only populated for top-level scalar values; nested mappings do
        #: not pollute this dict.
        self.scalar_styles: dict[str, str | None] = {}

    def construct_document(self, node: yaml.Node) -> object:  # type: ignore[override]
        # Capture top-level scalar styles before construction.  This runs
        # once for the root node, so only top-level mapping values are
        # recorded -- nested mappings do not overwrite top-level entries.
        if isinstance(node, yaml.MappingNode):
            for key_node, value_node in node.value:
                if isinstance(key_node, yaml.ScalarNode) and isinstance(
                    value_node, yaml.ScalarNode
                ):
                    self.scalar_styles[key_node.value] = value_node.style
        return super().construct_document(node)

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict:  # type: ignore[override]
        if not isinstance(node, yaml.MappingNode):
            raise yaml.constructor.ConstructorError(
                None,
                None,
                "expected a mapping node",
                node.start_mark,
            )
        seen: set[object] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                if key in seen:
                    raise ConstructorError(
                        None,
                        None,
                        f"duplicate key: {key!r}",
                        key_node.start_mark,
                    )
                seen.add(key)
            except TypeError:
                # Unhashable key (e.g. list or dict) - produce a structured
                # diagnostic rather than letting TypeError escape.
                raise ConstructorError(
                    None,
                    None,
                    f"unhashable mapping key: {key!r}",
                    key_node.start_mark,
                ) from None
        return super().construct_mapping(node, deep=deep)


def parse_front_matter(
    raw_body: str, *, collect_unknown_fields: bool = False
) -> ParsedFrontMatter:
    """Parse and validate YAML front matter from an Issue body.

    Parameters
    ----------
    raw_body:
        The raw Issue body (front matter included).
    collect_unknown_fields:
        When ``False`` (default), unknown fields raise
        :class:`FrontMatterError`.  When ``True``, unknown fields are
        collected in :attr:`ParsedFrontMatter.unknown_fields` and only
        known fields are returned in ``fields``, allowing the caller to
        continue processing known fields and body.

    Returns
    -------
    ParsedFrontMatter
        Validated fields and the Markdown body after front matter.

    Raises
    ------
    FrontMatterError
        If the envelope, YAML, size, duplicate-key, custom-tag rules are
        violated, or (when ``collect_unknown_fields=False``) an unknown
        field is present.
    """
    # Split by any line ending (CRLF, CR, or LF).  This produces the same
    # lines as the previous normalize-then-split approach, but preserves
    # access to the raw bytes (including ``\r``) for the size check.
    lines = _LINE_ENDING_RE.split(raw_body)
    line_endings = list(_LINE_ENDING_RE.finditer(raw_body))

    # --- First line must be exactly '---' ---------------------------------
    if not lines or lines[0] != "---":
        raise FrontMatterError(
            code="FRONT_MATTER_MISSING",
            message="Issue body must start with a '---' front-matter delimiter",
        )

    # --- Find closing delimiter -------------------------------------------
    close_index: int | None = None
    for i in range(1, len(lines)):
        if lines[i] == "---":
            close_index = i
            break

    if close_index is None:
        raise FrontMatterError(
            code="FRONT_MATTER_UNCLOSED",
            message="Front matter is missing a closing '---' delimiter",
        )

    # --- 16 KiB UTF-8 size check (raw bytes, before CRLF normalization) ---
    # The size limit must be evaluated on the original front-matter bytes,
    # including ``\r`` characters that CRLF/CR line endings contribute.
    # Normalization (CRLF→LF, CR→LF) would shrink the byte count and could
    # hide an oversized payload.
    if close_index > 1 and line_endings:
        fm_start = line_endings[0].end()
        fm_end = line_endings[close_index - 1].start()
        raw_fm_content = raw_body[fm_start:fm_end]
    else:
        raw_fm_content = ""
    raw_fm_bytes = raw_fm_content.encode("utf-8")
    if len(raw_fm_bytes) > FRONT_MATTER_MAX_BYTES:
        raise FrontMatterError(
            code="FRONT_MATTER_TOO_LARGE",
            message=(
                f"Front matter exceeds {FRONT_MATTER_MAX_BYTES} bytes "
                f"({len(raw_fm_bytes)} bytes)"
            ),
        )

    # --- Extract front-matter content and body (normalized) --------------
    fm_lines = lines[1:close_index]
    fm_content = "\n".join(fm_lines)

    # Body starts after the closing delimiter; consume exactly one leading
    # newline so the Markdown body begins cleanly.
    body_lines = lines[close_index + 1 :]
    if body_lines and body_lines[0] == "":
        body_lines = body_lines[1:]
    body = "\n".join(body_lines)

    # --- Parse YAML with strict safe loader -------------------------------
    # An explicit loader instance is used (instead of ``yaml.load``) so that
    # top-level scalar style metadata captured by ``construct_document``
    # remains accessible after parsing.
    try:
        loader = _StrictYAMLLoader(fm_content)
        try:
            data = loader.get_single_data()
            scalar_styles = dict(loader.scalar_styles)
        finally:
            loader.dispose()
    except ConstructorError as exc:
        if "duplicate key" in str(exc).lower():
            raise FrontMatterError(
                code="FRONT_MATTER_DUPLICATE_KEY",
                message=f"Duplicate key in front matter: {exc}",
            ) from exc
        # Custom tags and other constructor errors
        raise FrontMatterError(
            code="FRONT_MATTER_INVALID_YAML",
            message=f"Invalid YAML in front matter: {exc}",
        ) from exc
    except yaml.YAMLError as exc:
        raise FrontMatterError(
            code="FRONT_MATTER_INVALID_YAML",
            message=f"Invalid YAML in front matter: {exc}",
        ) from exc

    # --- Must be a mapping ------------------------------------------------
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise FrontMatterError(
            code="FRONT_MATTER_NOT_MAPPING",
            message=f"Front matter must be a YAML mapping, got {type(data).__name__}",
        )

    # --- Reject or collect unknown fields -------------------------------
    unknown_fields: list[str] = []
    known_fields: dict[str, object] = {}
    for key, value in data.items():
        if key in ALLOWED_FIELDS:
            known_fields[key] = value
        else:
            if collect_unknown_fields:
                unknown_fields.append(str(key))
            else:
                raise FrontMatterError(
                    code="FRONT_MATTER_UNKNOWN_FIELD",
                    message=f"Unknown field in front matter: {key!r}",
                    field=str(key),
                )

    return ParsedFrontMatter(
        fields=known_fields,
        body=body,
        unknown_fields=unknown_fields,
        scalar_styles=scalar_styles,
    )
