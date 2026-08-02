"""Blog detail compiler - the primary content seam for Ticket 04.

Takes immutable ``IssueSnapshot`` values and explicit ``Settings``, applies
the Issue Content Contract v1 selection and validation rules, renders a
GFM-compatible Markdown subset, sanitizes the result, and produces compiled
``BlogPost`` values with accumulated diagnostics.

Selection rules:
- Pull Requests are excluded.
- Unauthorized authors produce a warning and are ignored.
- Issues without ``published`` are ignored without body parsing.
- Published, authorized Issues must have exactly one supported ``type:*``
  label.  Unknown or multiple type labels are errors.  Non-Blog types
  (``type:idea``, ``type:about``) are silently skipped.

Validation rules (Issue Content Contract v1):
- Front-matter envelope: ``---`` delimiters, YAML mapping, safe loader,
  custom-tag rejection, duplicate-key rejection, 16 KiB UTF-8 limit,
  unknown-field rejection.
- Fields: slug (required, string, ``^[a-z0-9]+(?:-[a-z0-9]+)*$``, 1-80 chars,
  unique, not reserved), description (required, string, non-empty, no control
  chars including U+2028/U+2029, no ``<``/``>``, ≤300 code points),
  created_date (required, ``YYYY-MM-DD``).
- Title: non-empty (from Issue title).
- Body: non-empty after front-matter removal.
- Tags: ``tag:*`` label keys must match ``^[a-z0-9]+(?:-[a-z0-9]+)*$`` and
  be 1-50 chars.

All detectable errors are accumulated and returned together.  Any error
prevents detail rendering (``posts`` is empty when ``has_errors`` is True).

NFC normalization + casefold is used for author and label matching.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Sequence
from datetime import datetime

from marko import Markdown
from marko.ext.gfm import GFM

from .build_result import Diagnostic
from .config import Settings
from .models.blog_post import BlogCompilationResult, BlogPost, BlogTag
from .models.issue_snapshot import IssueSnapshot
from .utils.frontmatter import FrontMatterError, parse_front_matter
from .utils.html_sanitizer import sanitize_html

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Supported content-type label values (the part after ``type:``).
_SUPPORTED_TYPES: frozenset[str] = frozenset({"blog", "idea", "about"})

#: Pattern for valid Blog slugs and tag keys.
_KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

#: Pattern for valid ``created_date`` format.
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: Maximum slug length.
_SLUG_MAX_LEN: int = 80

#: Maximum tag key length.
_TAG_MAX_LEN: int = 50

#: Maximum description length in Unicode code points.
_DESC_MAX_CODEPOINTS: int = 300

#: Reserved Blog-detail slugs that collide with pagination or other routes.
#:
#: Ticket04 tracer scope: only the known ``/blog/page/`` collision is
#: guarded here.  A dynamic RouteRegistry that derives the reserved set
#: from every registered site page is Ticket18's responsibility.
_RESERVED_SLUGS: frozenset[str] = frozenset({"page"})


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def _normalize(value: str) -> str:
    """NFC normalize and casefold for case-insensitive comparison."""
    return unicodedata.normalize("NFC", value).casefold()


def _extract_label_prefix(labels: tuple[str, ...], prefix: str) -> list[str]:
    """Extract values from labels matching *prefix* (NFC + casefold).

    Returns the lower-cased value after the prefix for each matching label.
    """
    result: list[str] = []
    prefix_norm = prefix  # already lower-case
    for label in labels:
        normalized = _normalize(label)
        if normalized.startswith(prefix_norm):
            result.append(normalized[len(prefix_norm) :])
    return result


# ---------------------------------------------------------------------------
# Default markdown renderer
# ---------------------------------------------------------------------------

_default_markdown = Markdown(extensions=[GFM])


def _default_render_markdown(text: str) -> str:
    """Render Markdown to HTML using marko with GFM (documented subset)."""
    return _default_markdown.convert(text)


# ---------------------------------------------------------------------------
# BlogCompiler
# ---------------------------------------------------------------------------


class BlogCompiler:
    """Compiles published Blog Issue snapshots into ``BlogPost`` values.

    The compiler is the primary content seam: snapshots and settings go in,
    a ``BlogCompilationResult`` comes out.  No PyGithub object, label
    interpretation, YAML parsing, or auxiliary slug map crosses this seam.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        markdown_renderer: Callable[[str], str] | None = None,
        sanitizer: Callable[[str], str] | None = None,
    ) -> None:
        self._settings = settings
        self._render_markdown = markdown_renderer or _default_render_markdown
        self._sanitize = sanitizer or sanitize_html

    def compile(self, snapshots: Sequence[IssueSnapshot]) -> BlogCompilationResult:
        """Compile Issue snapshots into Blog posts with diagnostics.

        Returns a ``BlogCompilationResult``.  When any error is present,
        ``posts`` is empty (any error prevents detail rendering).
        """
        diagnostics: list[Diagnostic] = []
        compiled: list[BlogPost] = []
        # Track all valid slug candidates for duplicate/reserved checks,
        # even when the same Issue has other local errors.
        slug_candidates: list[tuple[str, int]] = []

        for snap in snapshots:
            self._process_snapshot(snap, diagnostics, compiled, slug_candidates)

        # --- Reserved and duplicate slug checks (after all processing) ----
        self._check_reserved_slugs(slug_candidates, diagnostics)
        self._check_duplicate_slugs(slug_candidates, diagnostics)

        has_errors = any(d.severity == "error" for d in diagnostics)
        posts = tuple(compiled) if not has_errors else ()
        return BlogCompilationResult(
            posts=posts,
            diagnostics=tuple(diagnostics),
        )

    # --- Individual snapshot processing ----------------------------------

    def _process_snapshot(
        self,
        snap: IssueSnapshot,
        diagnostics: list[Diagnostic],
        compiled: list[BlogPost],
        slug_candidates: list[tuple[str, int]],
    ) -> None:
        # Pull Requests are excluded without diagnostics.
        if snap.is_pull_request:
            return

        # Unauthorized authors: warn and ignore.
        if not self._is_allowed_author(snap.author):
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="UNAUTHORIZED_AUTHOR",
                    message=(
                        f"Issue #{snap.number} author {snap.author!r} is not "
                        f"in allowed_authors"
                    ),
                    issue_number=snap.number,
                )
            )
            return

        # Unpublished Issues are ignored without parsing.
        if not self._is_published(snap.labels):
            return

        # Type label cardinality check.
        type_values = _extract_label_prefix(snap.labels, "type:")
        supported = [t for t in type_values if t in _SUPPORTED_TYPES]
        unsupported = [t for t in type_values if t not in _SUPPORTED_TYPES]

        has_type_error = False
        if not type_values:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TYPE_LABEL_MISSING",
                    message=f"Issue #{snap.number} has no type:* label",
                    issue_number=snap.number,
                )
            )
            has_type_error = True
        else:
            # Cardinality: exactly one type:* label of any kind.  More than
            # one (even if some are unknown) is TYPE_LABEL_MULTIPLE.
            if len(type_values) > 1:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TYPE_LABEL_MULTIPLE",
                        message=(
                            f"Issue #{snap.number} has multiple type labels: "
                            f"{type_values}"
                        ),
                        issue_number=snap.number,
                    )
                )
                has_type_error = True
            if unsupported:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="TYPE_LABEL_UNKNOWN",
                        message=(
                            f"Issue #{snap.number} has unknown type label(s): "
                            f"{unsupported}"
                        ),
                        issue_number=snap.number,
                    )
                )
                has_type_error = True

        if has_type_error:
            return

        # Exactly one supported type.  Non-Blog types are silently skipped.
        if supported[0] != "blog":
            return

        # --- Blog compilation -------------------------------------------
        self._compile_blog_post(snap, diagnostics, compiled, slug_candidates)

    # --- Blog post compilation -------------------------------------------

    def _compile_blog_post(
        self,
        snap: IssueSnapshot,
        diagnostics: list[Diagnostic],
        compiled: list[BlogPost],
        slug_candidates: list[tuple[str, int]],
    ) -> None:
        """Compile a single Blog snapshot, accumulating all detectable errors."""
        has_error = False

        # --- Title validation -------------------------------------------
        if not snap.title or not snap.title.strip():
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="TITLE_EMPTY",
                    message=f"Issue #{snap.number} has an empty title",
                    issue_number=snap.number,
                    field="title",
                )
            )
            has_error = True

        # --- Front matter parsing ---------------------------------------
        parsed = None
        try:
            parsed = parse_front_matter(snap.body, collect_unknown_fields=True)
        except FrontMatterError as exc:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code=exc.code,
                    message=f"Issue #{snap.number}: {exc.message}",
                    issue_number=snap.number,
                    field=exc.field,
                )
            )
            has_error = True

        # --- Field validation (only if front matter parsed) -------------
        slug: str | None = None
        if parsed is not None:
            fields = parsed.fields
            body = parsed.body

            # Report unknown fields without blocking downstream validation.
            if parsed.unknown_fields:
                for key in parsed.unknown_fields:
                    diagnostics.append(
                        Diagnostic(
                            severity="error",
                            code="FRONT_MATTER_UNKNOWN_FIELD",
                            message=(
                                f"Issue #{snap.number}: Unknown field in "
                                f"front matter: {key!r}"
                            ),
                            issue_number=snap.number,
                            field=key,
                        )
                    )
                has_error = True

            errors = self._validate_fields(
                snap.number, fields, body, snap.labels, parsed.scalar_styles
            )
            if errors:
                diagnostics.extend(errors)
                has_error = True

            # Extract valid slug candidate for duplicate/reserved checks
            # even when other local errors exist.
            slug_val = fields.get("slug")
            if (
                isinstance(slug_val, str)
                and _KEBAB_RE.fullmatch(slug_val)
                and len(slug_val) <= _SLUG_MAX_LEN
            ):
                slug = slug_val

        if has_error:
            if slug is not None:
                slug_candidates.append((slug, snap.number))
            return

        # --- Body rendering and sanitization ----------------------------
        # At this point, parsed and slug are guaranteed non-None because
        # has_error is False (no errors accumulated).
        if parsed is None or slug is None:  # pragma: no cover
            return

        # Catch markdown renderer and sanitizer collaborator exceptions
        # separately, converting each to a stable per-Issue Diagnostic so
        # errors accumulate and remaining Issues continue processing.
        try:
            rendered_html = self._render_markdown(parsed.body)
        except Exception:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="MARKDOWN_RENDER_FAILED",
                    message=f"Issue #{snap.number}: Markdown rendering failed",
                    issue_number=snap.number,
                    field="body",
                )
            )
            slug_candidates.append((slug, snap.number))
            return

        try:
            body_html = self._sanitize(rendered_html)
        except Exception:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="SANITIZER_FAILED",
                    message=f"Issue #{snap.number}: HTML sanitization failed",
                    issue_number=snap.number,
                    field="body",
                )
            )
            slug_candidates.append((slug, snap.number))
            return

        # --- Tag extraction ---------------------------------------------
        tags = self._extract_tags(snap.labels)

        post = BlogPost(
            issue_number=snap.number,
            title=snap.title,
            slug=slug,
            description=str(fields["description"]),
            created_date=str(fields["created_date"]),
            published_at=snap.created_at,
            updated_at=snap.updated_at,
            tags=tags,
            body_html=body_html,
            canonical_path=f"/blog/{slug}/",
        )
        compiled.append(post)
        slug_candidates.append((slug, snap.number))

    # --- Field validation -----------------------------------------------

    def _validate_fields(
        self,
        issue_number: int,
        fields: dict[str, object],
        body: str,
        labels: tuple[str, ...],
        scalar_styles: dict[str, str | None],
    ) -> list[Diagnostic]:
        """Validate front-matter fields, body, and tags.  Returns errors."""
        errors: list[Diagnostic] = []

        # --- Slug -------------------------------------------------------
        if "slug" not in fields:
            errors.append(
                Diagnostic(
                    severity="error",
                    code="SLUG_MISSING",
                    message=f"Issue #{issue_number}: slug is required for Blog",
                    issue_number=issue_number,
                    field="slug",
                )
            )
        else:
            slug_val = fields["slug"]
            if not isinstance(slug_val, str):
                errors.append(
                    Diagnostic(
                        severity="error",
                        code="SLUG_INVALID",
                        message=(
                            f"Issue #{issue_number}: slug must be a string, "
                            f"got {type(slug_val).__name__}"
                        ),
                        issue_number=issue_number,
                        field="slug",
                    )
                )
            elif not _KEBAB_RE.fullmatch(slug_val) or len(slug_val) > _SLUG_MAX_LEN:
                errors.append(
                    Diagnostic(
                        severity="error",
                        code="SLUG_INVALID",
                        message=(
                            f"Issue #{issue_number}: slug {slug_val!r} must match "
                            f"^[a-z0-9]+(?:-[a-z0-9]+)*$ and be 1-{_SLUG_MAX_LEN} chars"
                        ),
                        issue_number=issue_number,
                        field="slug",
                    )
                )

        # --- Description ------------------------------------------------
        if "description" not in fields:
            errors.append(
                Diagnostic(
                    severity="error",
                    code="DESCRIPTION_MISSING",
                    message=f"Issue #{issue_number}: description is required",
                    issue_number=issue_number,
                    field="description",
                )
            )
        else:
            desc_val = fields["description"]
            if not isinstance(desc_val, str):
                errors.append(
                    Diagnostic(
                        severity="error",
                        code="DESCRIPTION_INVALID",
                        message=(
                            f"Issue #{issue_number}: description must be a "
                            f"string, got {type(desc_val).__name__}"
                        ),
                        issue_number=issue_number,
                        field="description",
                    )
                )
            else:
                desc_errors = self._validate_description(issue_number, desc_val)
                errors.extend(desc_errors)

        # --- created_date -----------------------------------------------
        if "created_date" not in fields:
            errors.append(
                Diagnostic(
                    severity="error",
                    code="CREATED_DATE_MISSING",
                    message=f"Issue #{issue_number}: created_date is required",
                    issue_number=issue_number,
                    field="created_date",
                )
            )
        else:
            date_val = fields["created_date"]
            # The YAML scalar style must be single- or double-quoted.
            # This rejects plain scalars (including ``!!str 2026-01-01``),
            # literal block (``|-``), and folded block (``>-``) -- all of
            # which construct to the same Python ``str`` but are not quoted.
            date_style = scalar_styles.get("created_date")
            if (
                not isinstance(date_val, str)
                or date_style not in ("'", '"')
                or not _DATE_RE.match(date_val)
            ):
                errors.append(
                    Diagnostic(
                        severity="error",
                        code="CREATED_DATE_INVALID",
                        message=(
                            f"Issue #{issue_number}: created_date must be a "
                            f"quoted YYYY-MM-DD string, got {date_val!r}"
                        ),
                        issue_number=issue_number,
                        field="created_date",
                    )
                )
            else:
                # Validate it's a real date.
                try:
                    datetime.strptime(date_val, "%Y-%m-%d")
                except ValueError:
                    errors.append(
                        Diagnostic(
                            severity="error",
                            code="CREATED_DATE_INVALID",
                            message=(
                                f"Issue #{issue_number}: created_date "
                                f"{date_val!r} is not a valid date"
                            ),
                            issue_number=issue_number,
                            field="created_date",
                        )
                    )

        # --- Body -------------------------------------------------------
        if not body or not body.strip():
            errors.append(
                Diagnostic(
                    severity="error",
                    code="BODY_EMPTY",
                    message=f"Issue #{issue_number}: body must be non-empty",
                    issue_number=issue_number,
                    field="body",
                )
            )

        # --- Tags -------------------------------------------------------
        tag_errors = self._validate_tags(issue_number, labels)
        errors.extend(tag_errors)

        return errors

    def _validate_description(self, issue_number: int, desc: str) -> list[Diagnostic]:
        """Validate the description field."""
        errors: list[Diagnostic] = []

        if not desc or not desc.strip():
            errors.append(
                Diagnostic(
                    severity="error",
                    code="DESCRIPTION_INVALID",
                    message=f"Issue #{issue_number}: description must be non-empty",
                    issue_number=issue_number,
                    field="description",
                )
            )
            return errors

        # No control characters, line separators, or paragraph separators.
        # Covers C0 (U+0000-U+001F), DEL (U+007F), C1 (U+0080-U+009F),
        # U+2028 (LINE SEPARATOR), and U+2029 (PARAGRAPH SEPARATOR).
        for i, ch in enumerate(desc):
            cp = ord(ch)
            if cp < 0x20 or (0x7F <= cp <= 0x9F) or ch in ("\u2028", "\u2029"):
                errors.append(
                    Diagnostic(
                        severity="error",
                        code="DESCRIPTION_INVALID",
                        message=(
                            f"Issue #{issue_number}: description contains "
                            f"a control character at position {i}"
                        ),
                        issue_number=issue_number,
                        field="description",
                    )
                )
                return errors

        # No angle brackets.
        if "<" in desc or ">" in desc:
            errors.append(
                Diagnostic(
                    severity="error",
                    code="DESCRIPTION_INVALID",
                    message=(
                        f"Issue #{issue_number}: description must not contain "
                        f"'<' or '>'"
                    ),
                    issue_number=issue_number,
                    field="description",
                )
            )
            return errors

        # Length check (Unicode code points).
        if len(desc) > _DESC_MAX_CODEPOINTS:
            errors.append(
                Diagnostic(
                    severity="error",
                    code="DESCRIPTION_TOO_LONG",
                    message=(
                        f"Issue #{issue_number}: description exceeds "
                        f"{_DESC_MAX_CODEPOINTS} code points "
                        f"({len(desc)})"
                    ),
                    issue_number=issue_number,
                    field="description",
                )
            )

        return errors

    def _validate_tags(
        self, issue_number: int, labels: tuple[str, ...]
    ) -> list[Diagnostic]:
        """Validate tag:* label keys."""
        errors: list[Diagnostic] = []
        tag_keys = _extract_label_prefix(labels, "tag:")
        for key in tag_keys:
            if not _KEBAB_RE.fullmatch(key) or len(key) > _TAG_MAX_LEN:
                errors.append(
                    Diagnostic(
                        severity="error",
                        code="TAG_INVALID",
                        message=(
                            f"Issue #{issue_number}: tag key {key!r} must match "
                            f"^[a-z0-9]+(?:-[a-z0-9]+)*$ and be 1-{_TAG_MAX_LEN} chars"
                        ),
                        issue_number=issue_number,
                        field="tags",
                    )
                )
        return errors

    # --- Tag extraction -------------------------------------------------

    def _extract_tags(self, labels: tuple[str, ...]) -> tuple[BlogTag, ...]:
        """Extract validated tag keys from tag:* labels as immutable BlogTag values.

        Each BlogTag carries its own display name (the normalized key) and
        canonical strict path (``/tags/{key}/``) so templates never decide
        between legacy and strict URL schemes.
        """
        tag_keys = _extract_label_prefix(labels, "tag:")
        # Deduplicate while preserving order.
        seen: set[str] = set()
        result: list[BlogTag] = []
        for key in tag_keys:
            if key not in seen:
                seen.add(key)
                result.append(BlogTag(name=key, path=f"/tags/{key}/"))
        return tuple(result)

    # --- Selection helpers ----------------------------------------------

    def _is_allowed_author(self, author: str) -> bool:
        author_norm = _normalize(author)
        return any(
            _normalize(a) == author_norm for a in self._settings.github.allowed_authors
        )

    def _is_published(self, labels: tuple[str, ...]) -> bool:
        return any(_normalize(label) == "published" for label in labels)

    # --- Reserved slug check -------------------------------------------

    def _check_reserved_slugs(
        self,
        slug_candidates: list[tuple[str, int]],
        diagnostics: list[Diagnostic],
    ) -> None:
        """Detect reserved slugs that collide with pagination or other routes."""
        for slug, issue_number in slug_candidates:
            if slug in _RESERVED_SLUGS:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="SLUG_RESERVED",
                        message=(
                            f"Issue #{issue_number}: slug {slug!r} is reserved "
                            f"and cannot be used for a Blog detail page"
                        ),
                        issue_number=issue_number,
                        field="slug",
                    )
                )

    # --- Duplicate slug check -------------------------------------------

    def _check_duplicate_slugs(
        self,
        slug_candidates: list[tuple[str, int]],
        diagnostics: list[Diagnostic],
    ) -> None:
        """Detect duplicate slugs among all valid slug candidates."""
        seen: dict[str, int] = {}
        for slug, issue_number in slug_candidates:
            if slug in seen:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code="SLUG_DUPLICATE",
                        message=(
                            f"Issue #{issue_number}: slug {slug!r} "
                            f"duplicates Issue #{seen[slug]}"
                        ),
                        issue_number=issue_number,
                        field="slug",
                    )
                )
            else:
                seen[slug] = issue_number
