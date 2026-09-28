from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import NoReturn

from .build_result import Diagnostic
from .config import Settings
from .content_validation import (
    CONTENT_TYPES,
    render_body,
    reserved_blog_slug,
    tag_key,
    validate_authored_content,
)
from .models.blog_post import BlogPost, BlogTag, blog_post_sort_key
from .models.content import AboutPage, ContentCompilationResult, Idea, IdeaTag
from .models.issue_snapshot import IssueSnapshot
from .routes import RouteCollisionError, RouteRegistry
from .utils.frontmatter import FrontMatterError, ParsedFrontMatter, parse_front_matter


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
    """Extract text from sanitized HTML, preserving inline adjacency."""

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

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._BREAKS:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._BREAKS:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _body_description(body_html: str) -> str:
    parser = _VisibleBodyText()
    parser.feed(body_html)
    parser.close()
    return " ".join("".join(parser.parts).split())[:50]


class _SkipIssueError(Exception):
    """Stop compiling one Issue; its diagnostics are already recorded."""


class ContentCompiler:
    """Compile Issue Content into Blog, Idea and About models.

    A content error in one Issue skips that Issue (``result.skipped``); only
    problems with the configured About selection stop the build.
    """

    def __init__(self, settings: Settings, *, route_registry: RouteRegistry) -> None:
        self._settings = settings
        self._routes = route_registry
        self._diagnostics: list[Diagnostic] = []
        self._skipped: list[int] = []
        self._slugs: dict[str, int] = {}

    def compile(self, snapshots: Sequence[IssueSnapshot]) -> ContentCompilationResult:
        self._diagnostics = []
        self._skipped = []
        self._slugs = {}
        blogs: list[BlogPost] = []
        ideas: list[Idea] = []
        abouts: list[AboutPage] = []
        configured = self._settings.about.issue_number
        configured_seen = False

        # Oldest first, so an earlier Issue keeps a contested slug or About role.
        for snapshot in sorted(snapshots, key=lambda item: item.number):
            is_about = snapshot.number == configured
            configured_seen = configured_seen or is_about
            try:
                page = self._compile_one(snapshot, is_about=is_about)
            except _SkipIssueError:
                if not is_about:
                    self._skipped.append(snapshot.number)
                continue
            if isinstance(page, BlogPost):
                blogs.append(page)
            elif isinstance(page, Idea):
                ideas.append(page)
            elif isinstance(page, AboutPage):
                abouts.append(page)

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
        for extra in abouts[1:]:
            self._diagnostics.append(
                self._error(
                    extra,
                    "ABOUT_DUPLICATE",
                    f"another About Issue (#{abouts[0].issue_number}) is already "
                    "published; set about.issue_number to choose one",
                    "labels",
                )
            )
            self._skipped.append(extra.issue_number)

        return ContentCompilationResult(
            blogs=tuple(sorted(blogs, key=blog_post_sort_key, reverse=True)),
            ideas=tuple(
                sorted(
                    ideas,
                    key=lambda idea: (idea.published_at, idea.issue_number),
                    reverse=True,
                )
            ),
            about=abouts[0] if abouts else None,
            diagnostics=tuple(self._diagnostics),
            skipped=tuple(sorted(self._skipped)),
        )

    def _compile_one(
        self, snapshot: IssueSnapshot, *, is_about: bool
    ) -> BlogPost | Idea | AboutPage | None:
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
        section = "ideas" if content_type == "idea" else content_type
        if section != "blog" and getattr(self._routes.sections, section) is None:
            self._diagnostics.append(
                Diagnostic(
                    "warning",
                    "PAGE_OFF",
                    f"Issue #{snapshot.number}: is type:{content_type} but "
                    f"pages.{section} is false; it is not published",
                    snapshot.number,
                    "labels",
                )
            )
            return None
        if is_about and content_type != "about":
            self._fail(snapshot, "ABOUT_TYPE_INVALID", "must use the type:about label")
        if not is_about and content_type == "about":
            configured = self._settings.about.issue_number
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
        slug = str(parsed.fields.get("slug", snapshot.number))
        if content_type == "blog":
            self._claim_slug(snapshot, slug)
        description = (
            str(parsed.fields["description"])
            if "description" in parsed.fields
            else _body_description(body_html)
        )
        created_date = (
            datetime.strptime(str(parsed.fields["created_date"]), "%Y-%m-%d")
            .date()
            .isoformat()
            if "created_date" in parsed.fields
            else snapshot.created_at.astimezone(UTC).date().isoformat()
        )
        tags_on = self._routes.sections.tags is not None
        try:
            if content_type == "blog":
                return BlogPost(
                    issue_number=snapshot.number,
                    title=snapshot.title,
                    slug=slug,
                    description=description,
                    created_date=created_date,
                    published_at=snapshot.created_at,
                    updated_at=snapshot.updated_at,
                    tags=tuple(
                        BlogTag(
                            name,
                            tag_key(name),
                            self._routes.tag(tag_key(name)) if tags_on else None,
                        )
                        for name in tags
                    ),
                    body_html=body_html,
                    route=self._routes.blog_detail(slug),
                )
            if content_type == "idea":
                return Idea(
                    issue_number=snapshot.number,
                    title=snapshot.title,
                    description=description,
                    created_date=created_date,
                    published_at=snapshot.created_at,
                    updated_at=snapshot.updated_at,
                    tags=tuple(IdeaTag(name) for name in tags),
                    body_html=body_html,
                    route=self._routes.idea(snapshot.number),
                )
            return AboutPage(
                issue_number=snapshot.number,
                title=snapshot.title,
                description=description,
                created_date=created_date,
                body_html=body_html,
                route=self._routes.about(),
            )
        except (RouteCollisionError, ValueError) as exc:
            self._fail(snapshot, "ROUTE_COLLISION", str(exc), "route")
        return None

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
            parsed = parse_front_matter(snapshot.body, collect_unknown_fields=True)
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
        if reserved := reserved_blog_slug(slug):
            self._check(snapshot, [reserved])
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
                self._error(snapshot, error.code, error.message, error.field)
            )
        raise _SkipIssueError

    def _fail(
        self,
        snapshot: IssueSnapshot,
        code: str,
        message: str,
        field: str | None = None,
    ) -> NoReturn:
        self._diagnostics.append(self._error(snapshot, code, message, field))
        raise _SkipIssueError

    def _allowed(self, author: str) -> bool:
        return any(
            _normalize(author) == _normalize(value)
            for value in self._settings.github.allowed_authors
        )

    @staticmethod
    def _published(labels: tuple[str, ...]) -> bool:
        return any(_normalize(label) == "published" for label in labels)

    @staticmethod
    def _error(
        item: IssueSnapshot | AboutPage,
        code: str,
        message: str,
        field: str | None = None,
    ) -> Diagnostic:
        number = item.number if isinstance(item, IssueSnapshot) else item.issue_number
        return Diagnostic("error", code, f"Issue #{number}: {message}", number, field)
