from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from datetime import UTC
from html.parser import HTMLParser

from .build_result import Diagnostic
from .config import Settings
from .content_validation import (
    CONTENT_TYPES,
    render_body,
    reserved_blog_slug,
    valid_slug,
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
    return [
        normalized[len(prefix) :]
        for label in labels
        if (normalized := _normalize(label)).startswith(prefix)
    ]


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


class ContentCompiler:
    """Compile the single Issue Content format into Blog, Idea, and About models."""

    def __init__(
        self,
        settings: Settings,
        *,
        route_registry: RouteRegistry,
    ) -> None:
        self._settings = settings
        self._routes = route_registry

    def compile(self, snapshots: Sequence[IssueSnapshot]) -> ContentCompilationResult:
        diagnostics: list[Diagnostic] = []
        blogs: list[BlogPost] = []
        ideas: list[Idea] = []
        about_candidates: list[AboutPage] = []
        slug_candidates: list[tuple[str, int]] = []
        configured_number = self._settings.about.issue_number
        configured_seen = False

        for snapshot in snapshots:
            is_configured_about = snapshot.number == configured_number
            if is_configured_about:
                configured_seen = True

            if snapshot.is_pull_request:
                if is_configured_about:
                    diagnostics.append(
                        self._error(
                            snapshot,
                            "ABOUT_IS_PULL_REQUEST",
                            "Configured About Issue is a Pull Request",
                        )
                    )
                continue
            if not self._allowed(snapshot.author):
                code = (
                    "ABOUT_UNAUTHORIZED"
                    if is_configured_about
                    else "UNAUTHORIZED_AUTHOR"
                )
                severity = "error" if is_configured_about else "warning"
                diagnostics.append(
                    Diagnostic(
                        severity,
                        code,
                        f"Issue #{snapshot.number} author is not allowed",
                        snapshot.number,
                        "author",
                    )
                )
                continue
            if not self._published(snapshot.labels):
                if is_configured_about:
                    diagnostics.append(
                        self._error(
                            snapshot,
                            "ABOUT_UNPUBLISHED",
                            "Configured About Issue is not published",
                        )
                    )
                continue

            content_type = self._content_type(snapshot, diagnostics)
            if content_type is None:
                if is_configured_about:
                    diagnostics.append(
                        self._error(
                            snapshot,
                            "ABOUT_TYPE_INVALID",
                            "Configured About Issue must use type:about",
                        )
                    )
                continue
            if is_configured_about and content_type != "about":
                diagnostics.append(
                    self._error(
                        snapshot,
                        "ABOUT_TYPE_INVALID",
                        "Configured About Issue must use type:about",
                    )
                )
                continue

            parsed = self._parse(snapshot, diagnostics)
            if parsed is None:
                continue
            local_errors = validate_authored_content(
                snapshot.title,
                content_type,
                _label_values(snapshot.labels, "tag:"),
                parsed,
            )
            diagnostics.extend(
                self._error(snapshot, d.code, d.message, d.field) for d in local_errors
            )

            slug = parsed.fields.get("slug", str(snapshot.number))
            if content_type == "blog" and isinstance(slug, str) and valid_slug(slug):
                slug_candidates.append((slug, snapshot.number))
            if local_errors:
                continue

            body_html, body_errors = render_body(parsed.body)
            diagnostics.extend(
                self._error(snapshot, d.code, d.message, d.field) for d in body_errors
            )
            if body_html is None:
                continue
            description = (
                str(parsed.fields["description"])
                if "description" in parsed.fields
                else _body_description(body_html)
            )
            created_date = (
                str(parsed.fields["created_date"])
                if "created_date" in parsed.fields
                else snapshot.created_at.astimezone(UTC).date().isoformat()
            )

            try:
                if content_type == "blog":
                    route = self._routes.blog_detail(str(slug))
                    tags = tuple(
                        BlogTag(name, self._routes.tag(name).canonical_path)
                        for name in dict.fromkeys(
                            _label_values(snapshot.labels, "tag:")
                        )
                    )
                    blogs.append(
                        BlogPost(
                            issue_number=snapshot.number,
                            title=snapshot.title,
                            slug=str(slug),
                            description=description,
                            created_date=created_date,
                            published_at=snapshot.created_at,
                            updated_at=snapshot.updated_at,
                            tags=tags,
                            body_html=body_html,
                            route=route,
                        )
                    )
                elif content_type == "idea":
                    route = self._routes.idea(snapshot.number)
                    ideas.append(
                        Idea(
                            issue_number=snapshot.number,
                            title=snapshot.title,
                            description=description,
                            created_date=created_date,
                            published_at=snapshot.created_at,
                            updated_at=snapshot.updated_at,
                            tags=tuple(
                                IdeaTag(name)
                                for name in dict.fromkeys(
                                    _label_values(snapshot.labels, "tag:")
                                )
                            ),
                            body_html=body_html,
                            route=route,
                        )
                    )
                else:
                    route = self._routes.about()
                    about_candidates.append(
                        AboutPage(
                            issue_number=snapshot.number,
                            title=snapshot.title,
                            description=description,
                            body_html=body_html,
                            route=route,
                        )
                    )
            except (RouteCollisionError, ValueError) as exc:
                diagnostics.append(
                    self._error(snapshot, "ROUTE_COLLISION", str(exc), "route")
                )

        if configured_number is not None and not configured_seen:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "ABOUT_MISSING",
                    f"Configured About Issue #{configured_number} was not found",
                    configured_number,
                )
            )

        configured_about = next(
            (
                page
                for page in about_candidates
                if configured_number is None or page.issue_number == configured_number
            ),
            None,
        )
        if len(about_candidates) > 1:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "ABOUT_DUPLICATE",
                    "More than one valid published About Issue exists",
                    about_candidates[1].issue_number,
                )
            )

        self._validate_blog_slugs(slug_candidates, diagnostics)
        has_errors = any(d.severity == "error" for d in diagnostics)
        if has_errors:
            return ContentCompilationResult(diagnostics=tuple(diagnostics))

        return ContentCompilationResult(
            blogs=tuple(
                sorted(
                    blogs,
                    key=blog_post_sort_key,
                    reverse=True,
                )
            ),
            ideas=tuple(
                sorted(
                    ideas,
                    key=lambda idea: (idea.published_at, idea.issue_number),
                    reverse=True,
                )
            ),
            about=configured_about,
            diagnostics=tuple(diagnostics),
        )

    def _content_type(
        self, snapshot: IssueSnapshot, diagnostics: list[Diagnostic]
    ) -> str | None:
        values = _label_values(snapshot.labels, "type:")
        unknown = [value for value in values if value not in CONTENT_TYPES]
        if not values:
            diagnostics.append(
                self._error(snapshot, "TYPE_LABEL_MISSING", "Issue has no type:* label")
            )
        if len(values) > 1:
            diagnostics.append(
                self._error(
                    snapshot, "TYPE_LABEL_MULTIPLE", "Issue has multiple type:* labels"
                )
            )
        if unknown:
            diagnostics.append(
                self._error(
                    snapshot,
                    "TYPE_LABEL_UNKNOWN",
                    f"Issue has unknown type labels: {unknown}",
                )
            )
        if len(values) != 1 or unknown:
            return None
        return values[0]

    def _parse(
        self, snapshot: IssueSnapshot, diagnostics: list[Diagnostic]
    ) -> ParsedFrontMatter | None:
        try:
            parsed = parse_front_matter(snapshot.body, collect_unknown_fields=True)
        except FrontMatterError as exc:
            diagnostics.append(
                Diagnostic(
                    "error",
                    exc.code,
                    f"Issue #{snapshot.number}: {exc.message}",
                    snapshot.number,
                    exc.field,
                )
            )
            return None
        for field in parsed.unknown_fields:
            diagnostics.append(
                self._error(
                    snapshot,
                    "FRONT_MATTER_UNKNOWN_FIELD",
                    f"Unknown front matter field: {field}",
                    field,
                )
            )
        return parsed

    def _validate_blog_slugs(
        self, candidates: list[tuple[str, int]], diagnostics: list[Diagnostic]
    ) -> None:
        seen: dict[str, int] = {}
        for slug, number in candidates:
            if reserved := reserved_blog_slug(slug):
                diagnostics.append(
                    Diagnostic(
                        reserved.severity,
                        reserved.code,
                        f"Issue #{number}: {reserved.message}",
                        number,
                        reserved.field,
                    )
                )
            if slug in seen:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "SLUG_DUPLICATE",
                        f"Issue #{number}: slug duplicates Issue #{seen[slug]}",
                        number,
                        "slug",
                    )
                )
            else:
                seen[slug] = number

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
        snapshot: IssueSnapshot, code: str, message: str, field: str | None = None
    ) -> Diagnostic:
        return Diagnostic(
            "error",
            code,
            f"Issue #{snapshot.number}: {message}",
            snapshot.number,
            field,
        )
