"""The Issue Content of a site: each entry with its address and its page HTML."""

from __future__ import annotations

from collections.abc import Sequence

from .build_result import Diagnostic
from .config import Settings
from .content_validation import render_body, tag_key
from .issue_content import ContentRules, Entry, compile_issues
from .models.blog_post import BlogPost, BlogTag
from .models.content import AboutPage, ContentCompilationResult, Idea, IdeaTag
from .models.issue_snapshot import IssueSnapshot
from .routes import RouteCollisionError, RouteRegistry

#: Content type -> the ``pages`` section that publishes it.
_SECTION = {"idea": "ideas", "about": "about"}


class ContentCompiler:
    """Compile Issue Content into the Blog, Idea and About pages of a site.

    Which Issues are published is decided by ``issue_content``; this adds what
    only a site has. An Issue of a section the Config turns off is left out
    with a warning, and one whose address is already taken is skipped.
    """

    def __init__(self, settings: Settings, *, route_registry: RouteRegistry) -> None:
        self._settings = settings
        self._routes = route_registry

    def compile(self, snapshots: Sequence[IssueSnapshot]) -> ContentCompilationResult:
        sections = self._routes.sections
        configured = self._settings.about.issue_number
        content = compile_issues(
            ContentRules(
                allowed_authors=tuple(self._settings.github.allowed_authors),
                about_issue_number=configured,
                off={
                    content_type: f"pages.{section} is false"
                    for content_type, section in _SECTION.items()
                    if getattr(sections, section) is None
                },
            ),
            snapshots,
        )
        diagnostics = list(content.diagnostics)
        skipped = set(content.skipped)
        pages: dict[int, BlogPost | Idea | AboutPage] = {}
        entries = [*content.blogs, *content.ideas]
        if content.about:
            entries.append(content.about)
        # Oldest first, so an earlier Issue keeps a contested address.
        for entry in sorted(entries, key=lambda item: item.issue_number):
            try:
                pages[entry.issue_number] = self._page(entry)
            except (RouteCollisionError, ValueError) as exc:
                number = entry.issue_number
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "ROUTE_COLLISION",
                        f"Issue #{number}: {exc}",
                        number,
                        "route",
                    )
                )
                if number != configured:
                    skipped.add(number)

        def kept[T: BlogPost | Idea | AboutPage](
            kind: type[T], items: Sequence[Entry]
        ) -> tuple[T, ...]:
            found = (pages.get(item.issue_number) for item in items)
            return tuple(page for page in found if isinstance(page, kind))

        abouts = kept(AboutPage, [content.about] if content.about else [])
        return ContentCompilationResult(
            blogs=kept(BlogPost, content.blogs),
            ideas=kept(Idea, content.ideas),
            about=abouts[0] if abouts else None,
            diagnostics=tuple(diagnostics),
            skipped=tuple(sorted(skipped)),
        )

    def _page(self, entry: Entry) -> BlogPost | Idea | AboutPage:
        base = self._routes.base
        # Links below the site's path need it; without one the HTML is the same.
        body_html = render_body(entry.body_markdown, base=base)[0] if base else None
        if body_html is None:
            body_html = entry.body_html
        if entry.type == "about":
            return AboutPage(
                issue_number=entry.issue_number,
                title=entry.title,
                description=entry.description,
                body_html=body_html,
                route=self._routes.about(),
            )
        if entry.type == "idea":
            return Idea(
                issue_number=entry.issue_number,
                title=entry.title,
                description=entry.description,
                created_date=entry.created_date,
                update_date=entry.update_date,
                published_at=entry.published_at,
                updated_at=entry.updated_at,
                tags=tuple(IdeaTag(name) for name in entry.tags),
                body_html=body_html,
                route=self._routes.idea(entry.issue_number),
            )
        tags_on = self._routes.sections.tags is not None
        return BlogPost(
            issue_number=entry.issue_number,
            title=entry.title,
            slug=entry.slug,
            description=entry.description,
            created_date=entry.created_date,
            update_date=entry.update_date,
            published_at=entry.published_at,
            updated_at=entry.updated_at,
            tags=tuple(
                BlogTag(
                    name,
                    tag_key(name),
                    self._routes.tag(tag_key(name)) if tags_on else None,
                )
                for name in entry.tags
            ),
            body_html=body_html,
            route=self._routes.blog_detail(entry.slug),
        )
