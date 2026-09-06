"""Authored content rules shared by Issue compilation and optional draft lint.

No Issue identity, defaults, publication selection, configuration or network I/O.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime

from marko import Markdown
from marko.ext.gfm import GFM

from .build_result import Diagnostic
from .utils.frontmatter import ParsedFrontMatter
from .utils.html_sanitizer import HTMLSanitizationError, sanitize_html

CONTENT_TYPES = frozenset({"blog", "idea", "about"})
_KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MARKDOWN = Markdown(extensions=[GFM])


def valid_slug(value: str) -> bool:
    return bool(_KEBAB_RE.fullmatch(value)) and len(value) <= 80


def reserved_blog_slug(value: str) -> Diagnostic | None:
    """Keep this check at the compiler's existing collection-validation stage."""
    if value == "page":
        return Diagnostic(
            "error", "SLUG_RESERVED", "slug 'page' is reserved", field="slug"
        )
    return None


def _valid_description(value: str) -> bool:
    if not value.strip() or len(value) > 300 or "<" in value or ">" in value:
        return False
    return not any(
        ord(char) < 32 or 0x7F <= ord(char) <= 0x9F or char in "\u2028\u2029"
        for char in value
    )


def _valid_date(value: object, style: str | None) -> bool:
    if (
        not isinstance(value, str)
        or style not in ("'", '"')
        or not _DATE_RE.fullmatch(value)
    ):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def validate_authored_content(
    title: str,
    content_type: str,
    tag_keys: Sequence[str],
    parsed: ParsedFrontMatter,
) -> tuple[Diagnostic, ...]:
    """Validate native title, resolved type/tags and explicit metadata only.

    Callers own input shape and type selection. Missing metadata stays missing;
    Issue label normalization and Local Draft field restrictions stay at intake.
    """
    errors: list[Diagnostic] = []
    fields = parsed.fields
    if not title.strip():
        errors.append(
            Diagnostic("error", "TITLE_EMPTY", "Title must be non-empty", field="title")
        )
    if not parsed.body.strip():
        errors.append(
            Diagnostic("error", "BODY_EMPTY", "Body must be non-empty", field="body")
        )

    description = fields.get("description")
    if "description" in fields and (
        not isinstance(description, str) or not _valid_description(description)
    ):
        code = (
            "DESCRIPTION_TOO_LONG"
            if isinstance(description, str) and len(description) > 300
            else "DESCRIPTION_INVALID"
        )
        errors.append(
            Diagnostic(
                "error",
                code,
                "description must be plain text of at most 300 characters",
                field="description",
            )
        )
    if "created_date" in fields and not _valid_date(
        fields["created_date"], parsed.scalar_styles.get("created_date")
    ):
        errors.append(
            Diagnostic(
                "error",
                "CREATED_DATE_INVALID",
                "created_date must be a quoted YYYY-MM-DD string",
                field="created_date",
            )
        )

    slug = fields.get("slug")
    if content_type == "blog":
        if "slug" in fields and (not isinstance(slug, str) or not valid_slug(slug)):
            errors.append(
                Diagnostic(
                    "error",
                    "SLUG_INVALID",
                    "slug must be lower-case kebab-case and at most 80 characters",
                    field="slug",
                )
            )
    elif "slug" in fields:
        errors.append(
            Diagnostic(
                "error",
                "SLUG_FORBIDDEN",
                f"slug is forbidden for {content_type.title()}",
                field="slug",
            )
        )

    for tag in tag_keys:
        if not _KEBAB_RE.fullmatch(tag) or len(tag) > 50:
            errors.append(
                Diagnostic(
                    "error", "TAG_INVALID", f"Invalid tag: {tag!r}", field="tags"
                )
            )
    if content_type == "about" and tag_keys:
        errors.append(
            Diagnostic(
                "error", "ABOUT_TAG_FORBIDDEN", "About must not have tags", field="tags"
            )
        )
    return tuple(errors)


def render_body(markdown: str) -> tuple[str | None, tuple[Diagnostic, ...]]:
    """Render the shared GFM subset then apply the existing HTML sanitizer.

    The returned HTML is a preview/compiled value, never replacement Markdown.
    """
    try:
        rendered = _MARKDOWN.convert(markdown)
    except Exception:
        return None, (
            Diagnostic(
                "error",
                "MARKDOWN_RENDER_FAILED",
                "Markdown rendering failed",
                field="body",
            ),
        )
    try:
        return sanitize_html(rendered), ()
    except Exception as exc:
        # Only our controlled tag/position messages are safe to expose;
        # third-party exceptions may contain authored text or URL values.
        message = "HTML sanitization failed"
        if isinstance(exc, HTMLSanitizationError):
            message += f": {exc}"
        return None, (Diagnostic("error", "SANITIZER_FAILED", message, field="body"),)
