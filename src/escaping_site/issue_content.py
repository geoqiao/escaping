"""Issue Content: what the Issues of a repository publish, before any site.

Selection, the About choice, content rules and defaults of Issue Content v1.
Both outputs start here: ``escaping-site build`` gives each entry an address
and a page, ``escaping-site export`` writes it as a Markdown file. Nothing in
this module knows a URL, a page switch or a Theme, so the two cannot disagree
about which Issues are published.

A body is rendered and sanitized here only to judge it and to derive the
default description; a build renders it again for its own pages.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from operator import attrgetter
from typing import NoReturn

from .build_result import Diagnostic
from .content_validation import (
    CONTENT_TYPES,
    render_body,
    tag_key,
    validate_authored_content,
)
from .models.issue_snapshot import IssueSnapshot
from .utils.frontmatter import FrontMatterError, ParsedFrontMatter, parse_front_matter

IssueSource = Callable[[], Sequence[IssueSnapshot]]


@dataclass(frozen=True)
class ContentRules:
    """Who may publish and which Issue is About."""

    allowed_authors: tuple[str, ...]
    about_issue_number: int | None = None
    #: Content type -> why its Issues are left out, for a caller that has no
    #: place for them: ``{"idea": "pages.ideas is false"}``.
    off: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Entry:
    """One published Issue, every value resolved.

    ``slug`` is empty unless ``type`` is ``blog``. ``body_html`` is sanitized,
    with links as the author wrote them.
    """

    issue_number: int
    type: str
    title: str
    slug: str
    description: str
    created_date: str
    update_date: str
    published_at: datetime
    updated_at: datetime
    tags: tuple[str, ...]
    body_markdown: str
    body_html: str


@dataclass(frozen=True)
class IssueContent:
    """Published entries, Blog posts and Ideas newest first.

    ``skipped`` Issues are left out but do not stop a build or an export.
    """

    blogs: tuple[Entry, ...] = ()
    ideas: tuple[Entry, ...] = ()
    about: Entry | None = None
    diagnostics: tuple[Diagnostic, ...] = ()
    skipped: tuple[int, ...] = ()

    @property
    def has_errors(self) -> bool:
        """Errors that stop publication; a Skipped Issue's errors do not."""
        return any(
            d.severity == "error" and d.issue_number not in self.skipped
            for d in self.diagnostics
        )


def newest_first[T](items: Sequence[T]) -> tuple[T, ...]:
    # At the same time, the higher Issue number is the newer.
    return tuple(
        sorted(items, key=attrgetter("published_at", "issue_number"), reverse=True)
    )


def compile_issues(
    rules: ContentRules, snapshots: Sequence[IssueSnapshot]
) -> IssueContent:
    """Compile Issues into entries.

    A content error in one Issue skips that Issue; only problems with the
    configured About selection are errors of the whole run.
    """
    return _Compiler(rules).compile(snapshots)


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _label_values(labels: tuple[str, ...], prefix: str) -> list[str]:
    """Normalized values of ``prefix``-labels, e.g. ``type:Blog`` -> ``blog``."""
    return [
        normalized[len(prefix) :]
        for label in labels
        if (normalized := _normalize(label)).startswith(prefix)
    ]


def _tag_names(labels: tuple[str, ...]) -> list[str]:
    """Tag display names as written after ``tag:``, first spelling per key."""
    names: dict[str, str] = {}
    for label in labels:
        text = unicodedata.normalize("NFC", label)
        if text.casefold().startswith("tag:"):
            name = text[4:].strip()
            names.setdefault(tag_key(name), name)
    return list(names.values())


class _VisibleBodyText(HTMLParser):
    """Extract text from sanitized HTML, preserving inline adjacency.

    Mermaid source is left out: readers see the diagram, not its source.
    """

    _BREAKS = frozenset(
        [
            "p",
            "div",
            "br",
            "hr",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "ul",
            "ol",
            "li",
            "dl",
            "dt",
            "dd",
            "table",
            "thead",
            "tbody",
            "tfoot",
            "tr",
            "td",
            "th",
            "caption",
            "pre",
            "blockquote",
            "section",
            "article",
            "header",
            "footer",
            "aside",
            "nav",
            "figure",
            "figcaption",
            "details",
            "summary",
            "hgroup",
        ]
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._in_diagram = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "code" and "language-mermaid" in (dict(attrs).get("class") or ""):
            self._in_diagram = True
        if tag in self._BREAKS:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag == "code":
            self._in_diagram = False
        if tag in self._BREAKS:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self._in_diagram:
            self.parts.append(data)


def _body_description(body_html: str) -> str:
    parser = _VisibleBodyText()
    parser.feed(body_html)
    parser.close()
    return " ".join("".join(parser.parts).split())[:50]


class _SkipIssueError(Exception):
    """Stop compiling one Issue; its diagnostics are already recorded."""


def _date(value: datetime) -> str:
    return value.astimezone(UTC).date().isoformat()


def _authored_date(value: object) -> str:
    return datetime.strptime(str(value), "%Y-%m-%d").date().isoformat()


class _Compiler:
    def __init__(self, rules: ContentRules) -> None:
        self._rules = rules
        self._diagnostics: list[Diagnostic] = []
        self._skipped: list[int] = []
        self._slugs: dict[str, int] = {}

    def compile(self, snapshots: Sequence[IssueSnapshot]) -> IssueContent:
        entries: dict[str, list[Entry]] = {"blog": [], "idea": [], "about": []}
        configured = self._rules.about_issue_number
        configured_seen = False

        # Oldest first, so an earlier Issue keeps a contested slug or About role.
        for snapshot in sorted(snapshots, key=lambda item: item.number):
            is_about = snapshot.number == configured
            configured_seen = configured_seen or is_about
            try:
                entry = self._compile_one(snapshot, is_about=is_about)
            except _SkipIssueError:
                if not is_about:
                    self._skipped.append(snapshot.number)
                continue
            if entry is not None:
                entries[entry.type].append(entry)

        if configured is not None and not configured_seen:
            self._diagnostics.append(
                Diagnostic(
                    "error",
                    "ABOUT_MISSING",
                    f"about.issue_number #{configured} was not found",
                    configured,
                    "about.issue_number",
                )
            )
        abouts = entries["about"]
        for extra in abouts[1:]:
            self._diagnostics.append(
                _error(
                    extra.issue_number,
                    "ABOUT_DUPLICATE",
                    f"another About Issue (#{abouts[0].issue_number}) is already "
                    "published; set about.issue_number to choose one",
                    "labels",
                )
            )
            self._skipped.append(extra.issue_number)

        return IssueContent(
            blogs=newest_first(entries["blog"]),
            ideas=newest_first(entries["idea"]),
            about=abouts[0] if abouts else None,
            diagnostics=tuple(self._diagnostics),
            skipped=tuple(sorted(self._skipped)),
        )

    def _compile_one(self, snapshot: IssueSnapshot, *, is_about: bool) -> Entry | None:
        if snapshot.is_pull_request:
            if is_about:
                self._fail(snapshot, "ABOUT_IS_PULL_REQUEST", "is a Pull Request")
            return None
        if not self._allowed(snapshot.author):
            if is_about:
                self._fail(snapshot, "ABOUT_UNAUTHORIZED", "author is not allowed")
            self._diagnostics.append(
                Diagnostic(
                    "warning",
                    "UNAUTHORIZED_AUTHOR",
                    f"Issue #{snapshot.number}: author is not in allowed_authors",
                    snapshot.number,
                    "author",
                )
            )
            return None
        if not self._published(snapshot.labels):
            if is_about:
                self._fail(snapshot, "ABOUT_UNPUBLISHED", "has no published label")
            return None

        content_type = self._content_type(snapshot)
        if content_type in self._rules.off:
            self._diagnostics.append(
                Diagnostic(
                    "warning",
                    "PAGE_OFF",
                    f"Issue #{snapshot.number}: is type:{content_type} but "
                    f"{self._rules.off[content_type]}; it is not published",
                    snapshot.number,
                    "labels",
                )
            )
            return None
        if is_about and content_type != "about":
            self._fail(snapshot, "ABOUT_TYPE_INVALID", "must use the type:about label")
        if not is_about and content_type == "about":
            configured = self._rules.about_issue_number
            if configured is not None:
                self._fail(
                    snapshot,
                    "ABOUT_NOT_SELECTED",
                    f"is type:about but about.issue_number selects #{configured}",
                )

        parsed = self._parse(snapshot)
        tags = _tag_names(snapshot.labels)
        self._check(
            snapshot,
            validate_authored_content(snapshot.title, content_type, tags, parsed),
        )
        body_html, body_errors = render_body(parsed.body)
        self._check(snapshot, body_errors)
        if body_html is None:
            raise _SkipIssueError
        slug = ""
        if content_type == "blog":
            slug = str(parsed.fields.get("slug", snapshot.number))
            self._claim_slug(snapshot, slug)
        fields = parsed.fields
        created_date = (
            _authored_date(fields["created_date"])
            if "created_date" in fields
            else _date(snapshot.created_at)
        )
        if "update_date" in fields:
            update_date = _authored_date(fields["update_date"])
            if update_date < created_date:
                self._fail(
                    snapshot,
                    "UPDATE_DATE_BEFORE_CREATED",
                    f"update_date is before the creation date {created_date}",
                    "update_date",
                )
        else:
            # Not revised. GitHub's own time of change is ``updated_at``: it also
            # moves on a comment or a label, so it is no revision date.
            update_date = created_date
        return Entry(
            issue_number=snapshot.number,
            type=content_type,
            title=snapshot.title,
            slug=slug,
            description=(
                str(fields["description"])
                if "description" in fields
                else _body_description(body_html)
            ),
            created_date=created_date,
            update_date=update_date,
            published_at=snapshot.created_at,
            updated_at=snapshot.updated_at,
            tags=tuple(tags),
            body_markdown=parsed.body,
            body_html=body_html,
        )

    def _content_type(self, snapshot: IssueSnapshot) -> str:
        values = _label_values(snapshot.labels, "type:")
        unknown = [value for value in values if value not in CONTENT_TYPES]
        if unknown:
            self._fail(
                snapshot,
                "TYPE_LABEL_UNKNOWN",
                f"unknown type label type:{unknown[0]} "
                "(use type:blog, type:idea or type:about)",
                "labels",
            )
        if len(values) != 1:
            code = "TYPE_LABEL_MISSING" if not values else "TYPE_LABEL_MULTIPLE"
            self._fail(
                snapshot,
                code,
                "needs exactly one of type:blog, type:idea or type:about",
                "labels",
            )
        return values[0]

    def _parse(self, snapshot: IssueSnapshot) -> ParsedFrontMatter:
        try:
            parsed = parse_front_matter(snapshot.body)
        except FrontMatterError as exc:
            self._fail(snapshot, exc.code, exc.message, exc.field)
        self._check(
            snapshot,
            [
                Diagnostic(
                    "error",
                    "FRONT_MATTER_UNKNOWN_FIELD",
                    f"unknown front matter field: {field}",
                    field=field,
                )
                for field in parsed.unknown_fields
            ],
        )
        return parsed

    def _claim_slug(self, snapshot: IssueSnapshot, slug: str) -> None:
        owner = self._slugs.setdefault(slug, snapshot.number)
        if owner != snapshot.number:
            self._fail(
                snapshot,
                "SLUG_DUPLICATE",
                f"slug {slug!r} is already used by Issue #{owner}",
                "slug",
            )

    def _check(self, snapshot: IssueSnapshot, errors: Sequence[Diagnostic]) -> None:
        if not errors:
            return
        for error in errors:
            self._diagnostics.append(
                _error(snapshot.number, error.code, error.message, error.field)
            )
        raise _SkipIssueError

    def _fail(
        self,
        snapshot: IssueSnapshot,
        code: str,
        message: str,
        field: str | None = None,
    ) -> NoReturn:
        self._diagnostics.append(_error(snapshot.number, code, message, field))
        raise _SkipIssueError

    def _allowed(self, author: str) -> bool:
        return any(
            _normalize(author) == _normalize(value)
            for value in self._rules.allowed_authors
        )

    @staticmethod
    def _published(labels: tuple[str, ...]) -> bool:
        return any(_normalize(label) == "published" for label in labels)


def _error(
    number: int, code: str, message: str, field: str | None = None
) -> Diagnostic:
    return Diagnostic("error", code, f"Issue #{number}: {message}", number, field)
