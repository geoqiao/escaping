"""Immutable Blog detail models for the Site Compiler.

These are build-time, in-memory values produced by the Blog compiler. They
contain only plain Python types so no PyGithub object, label interpretation,
YAML parsing, or auxiliary slug map crosses into templates or rendering.

The models are sufficient for the Blog detail tracer (Ticket 04):
``BlogPost`` carries every field a detail page needs; ``BlogRoute`` maps a
canonical path to its output filesystem path; ``BlogCompilationResult``
bundles compiled posts with accumulated diagnostics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..build_result import Diagnostic


@dataclass(frozen=True)
class BlogTag:
    """Immutable tag value carrying its own display name and canonical path.

    Templates consume only ``name`` and ``path`` so they never need to
    decide between legacy and strict URL schemes.  The producer (strict
    BlogCompiler or legacy render_post adapter) is responsible for
    computing the correct path.

    Attributes:
        name: Display name for rendering (e.g. ``python``).
        path: Canonical URL path for the tag page
            (e.g. ``/tags/python/`` or ``/tag/python.html``).
    """

    name: str
    path: str


@dataclass(frozen=True)
class BlogPost:
    """Immutable compiled Blog post ready for detail rendering.

    Attributes:
        issue_number: GitHub Issue number — content identity and comment
            thread binding.
        title: Non-empty content title from the Issue title.
        slug: Lower-case ASCII kebab-case Blog route key from front matter.
        description: Plain-text summary (≤300 code points, no HTML).
        created_date: Authored creation date as ``YYYY-MM-DD``.
        published_at: GitHub Issue ``created_at`` — publication timestamp.
        updated_at: GitHub Issue ``updated_at`` — last update timestamp.
        tags: Tuple of immutable ``BlogTag`` values (name + canonical path).
        body_html: Sanitized GFM-rendered HTML body.
        canonical_path: Canonical URL path, e.g. ``/blog/{slug}/``.
    """

    issue_number: int
    title: str
    slug: str
    description: str
    created_date: str
    published_at: datetime
    updated_at: datetime
    tags: tuple[BlogTag, ...]
    body_html: str
    canonical_path: str

    @property
    def route(self) -> BlogRoute:
        """Return the fixed BlogRoute for this post.

        Blog routes are fixed: canonical ``/blog/{slug}/`` and output
        ``blog/{slug}/index.html``.  They are not configurable.
        """
        return BlogRoute(
            canonical_path=self.canonical_path,
            output_path=f"blog/{self.slug}/index.html",
        )


@dataclass(frozen=True)
class BlogRoute:
    """A single Blog detail route mapping canonical URL to output path.

    Attributes:
        canonical_path: Canonical URL path with trailing slash,
            e.g. ``/blog/my-slug/``.
        output_path: Relative filesystem path for the directory
            ``index.html``, e.g. ``blog/my-slug/index.html``.
    """

    canonical_path: str
    output_path: str


@dataclass(frozen=True)
class BlogCompilationResult:
    """Result of compiling Issue snapshots into Blog posts.

    Attributes:
        posts: Tuple of successfully compiled ``BlogPost`` values.
            Empty when validation errors prevent compilation.
        diagnostics: Tuple of accumulated diagnostics. Errors block
            rendering; warnings do not.
    """

    posts: tuple[BlogPost, ...] = field(default_factory=tuple)
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)

    @property
    def has_errors(self) -> bool:
        """True when any diagnostic is an error."""
        return any(d.severity == "error" for d in self.diagnostics)
