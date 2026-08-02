from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Sequence
from datetime import datetime

from marko import Markdown
from marko.ext.gfm import GFM

from .build_result import Diagnostic
from .config import Settings
from .models.blog_post import BlogPost, BlogTag
from .models.content import AboutPage, ContentCompilationResult, Idea
from .models.home_page import HomeProfile, HomeProfileLink
from .models.issue_snapshot import IssueSnapshot
from .routes import RouteCollisionError, RouteRegistry
from .utils.frontmatter import FrontMatterError, ParsedFrontMatter, parse_front_matter
from .utils.html_sanitizer import sanitize_html

_SUPPORTED_TYPES = frozenset({"blog", "idea", "about"})
_KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MARKDOWN = Markdown(extensions=[GFM])


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _label_values(labels: tuple[str, ...], prefix: str) -> list[str]:
    return [
        normalized[len(prefix) :]
        for label in labels
        if (normalized := _normalize(label)).startswith(prefix)
    ]


def _render_markdown(text: str) -> str:
    return _MARKDOWN.convert(text)


class ContentCompiler:
    """Compile the single Issue Content format into Blog, Idea, and About models."""

    def __init__(
        self,
        settings: Settings,
        *,
        markdown_renderer: Callable[[str], str] | None = None,
        sanitizer: Callable[[str], str] | None = None,
        route_registry: RouteRegistry | None = None,
    ) -> None:
        self._settings = settings
        self._render_markdown = markdown_renderer or _render_markdown
        self._sanitize = sanitizer or sanitize_html
        self._routes = route_registry or RouteRegistry(str(settings.site.url))

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
            local_errors = self._validate_common(snapshot, parsed)
            local_errors.extend(self._validate_type(snapshot, parsed, content_type))
            diagnostics.extend(local_errors)

            slug = parsed.fields.get("slug")
            if (
                content_type == "blog"
                and isinstance(slug, str)
                and self._valid_slug(slug)
            ):
                slug_candidates.append((slug, snapshot.number))
            if local_errors:
                continue

            body_html = self._compile_body(snapshot, parsed.body, diagnostics)
            if body_html is None:
                continue
            description = str(parsed.fields["description"])
            created_date = str(parsed.fields["created_date"])

            try:
                if content_type == "blog":
                    route = self._routes.blog_detail(str(slug))
                    tags = self._tags(snapshot.labels, register_routes=True)
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
                            canonical_path=route.canonical_path,
                            canonical_url=route.canonical_url,
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
                            tags=self._tags(snapshot.labels, register_routes=False),
                            body_html=body_html,
                            canonical_path=route.canonical_path,
                            canonical_url=route.canonical_url,
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
                            canonical_path=route.canonical_path,
                            canonical_url=route.canonical_url,
                            profile=HomeProfile(
                                avatar=self._settings.profile.avatar,
                                bio=self._settings.profile.bio,
                                links=tuple(
                                    HomeProfileLink(link.name, link.url)
                                    for link in self._settings.profile.links
                                ),
                            ),
                        )
                    )
            except (RouteCollisionError, ValueError) as exc:
                diagnostics.append(
                    self._error(snapshot, "ROUTE_COLLISION", str(exc), "route")
                )

        if not configured_seen:
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
                if page.issue_number == configured_number
            ),
            None,
        )
        other_about = [
            page for page in about_candidates if page.issue_number != configured_number
        ]
        if configured_about is not None and other_about:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "ABOUT_DUPLICATE",
                    "More than one valid published About Issue exists",
                    other_about[0].issue_number,
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
                    key=lambda post: (post.published_at, post.issue_number),
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
        unknown = [value for value in values if value not in _SUPPORTED_TYPES]
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

    def _validate_common(
        self, snapshot: IssueSnapshot, parsed: ParsedFrontMatter
    ) -> list[Diagnostic]:
        errors: list[Diagnostic] = []
        fields = parsed.fields
        if not snapshot.title.strip():
            errors.append(
                self._error(snapshot, "TITLE_EMPTY", "Title must be non-empty", "title")
            )
        if not parsed.body.strip():
            errors.append(
                self._error(snapshot, "BODY_EMPTY", "Body must be non-empty", "body")
            )

        description = fields.get("description")
        if description is None:
            errors.append(
                self._error(
                    snapshot,
                    "DESCRIPTION_MISSING",
                    "description is required",
                    "description",
                )
            )
        elif not isinstance(description, str) or not self._valid_description(
            description
        ):
            code = (
                "DESCRIPTION_TOO_LONG"
                if isinstance(description, str) and len(description) > 300
                else "DESCRIPTION_INVALID"
            )
            errors.append(
                self._error(
                    snapshot,
                    code,
                    "description must be plain text of at most 300 characters",
                    "description",
                )
            )

        created_date = fields.get("created_date")
        if created_date is None:
            errors.append(
                self._error(
                    snapshot,
                    "CREATED_DATE_MISSING",
                    "created_date is required",
                    "created_date",
                )
            )
        elif not self._valid_date(
            created_date, parsed.scalar_styles.get("created_date")
        ):
            errors.append(
                self._error(
                    snapshot,
                    "CREATED_DATE_INVALID",
                    "created_date must be a quoted YYYY-MM-DD string",
                    "created_date",
                )
            )
        return errors

    def _validate_type(
        self, snapshot: IssueSnapshot, parsed: ParsedFrontMatter, content_type: str
    ) -> list[Diagnostic]:
        errors: list[Diagnostic] = []
        slug = parsed.fields.get("slug")
        if content_type == "blog":
            if slug is None:
                errors.append(
                    self._error(
                        snapshot, "SLUG_MISSING", "slug is required for Blog", "slug"
                    )
                )
            elif not isinstance(slug, str) or not self._valid_slug(slug):
                errors.append(
                    self._error(
                        snapshot,
                        "SLUG_INVALID",
                        "slug must be lower-case kebab-case and at most 80 characters",
                        "slug",
                    )
                )
        elif slug is not None:
            errors.append(
                self._error(
                    snapshot,
                    "SLUG_FORBIDDEN",
                    f"slug is forbidden for {content_type.title()}",
                    "slug",
                )
            )

        tag_values = _label_values(snapshot.labels, "tag:")
        for tag in tag_values:
            if not _KEBAB_RE.fullmatch(tag) or len(tag) > 50:
                errors.append(
                    self._error(
                        snapshot, "TAG_INVALID", f"Invalid tag: {tag!r}", "tags"
                    )
                )
        if content_type == "about" and tag_values:
            errors.append(
                self._error(
                    snapshot, "ABOUT_TAG_FORBIDDEN", "About must not have tags", "tags"
                )
            )
        return errors

    def _compile_body(
        self, snapshot: IssueSnapshot, body: str, diagnostics: list[Diagnostic]
    ) -> str | None:
        try:
            rendered = self._render_markdown(body)
        except Exception:
            diagnostics.append(
                self._error(
                    snapshot,
                    "MARKDOWN_RENDER_FAILED",
                    "Markdown rendering failed",
                    "body",
                )
            )
            return None
        try:
            return self._sanitize(rendered)
        except Exception:
            diagnostics.append(
                self._error(
                    snapshot, "SANITIZER_FAILED", "HTML sanitization failed", "body"
                )
            )
            return None

    def _validate_blog_slugs(
        self, candidates: list[tuple[str, int]], diagnostics: list[Diagnostic]
    ) -> None:
        seen: dict[str, int] = {}
        for slug, number in candidates:
            if slug == "page":
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "SLUG_RESERVED",
                        f"Issue #{number}: slug 'page' is reserved",
                        number,
                        "slug",
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
    def _valid_slug(value: str) -> bool:
        return bool(_KEBAB_RE.fullmatch(value)) and len(value) <= 80

    @staticmethod
    def _valid_description(value: str) -> bool:
        if not value.strip() or len(value) > 300 or "<" in value or ">" in value:
            return False
        return not any(
            ord(char) < 32 or 0x7F <= ord(char) <= 0x9F or char in "\u2028\u2029"
            for char in value
        )

    @staticmethod
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

    def _tags(
        self, labels: tuple[str, ...], *, register_routes: bool
    ) -> tuple[BlogTag, ...]:
        names = dict.fromkeys(_label_values(labels, "tag:"))
        tags: list[BlogTag] = []
        for name in names:
            path = (
                self._routes.tag(name).canonical_path
                if register_routes
                else f"/tags/{name}/"
            )
            tags.append(BlogTag(name, path))
        return tuple(tags)

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
