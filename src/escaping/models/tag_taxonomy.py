from __future__ import annotations

from dataclasses import dataclass, field

from ..build_result import Diagnostic
from ..routes import Route
from .blog_post import BlogPost


@dataclass(frozen=True)
class Tag:
    """One Blog tag archive: display name, route key and its posts, newest first."""

    name: str
    key: str
    route: Route
    posts: tuple[BlogPost, ...]

    @property
    def count(self) -> int:
        return len(self.posts)

    @property
    def canonical_path(self) -> str:
        return self.route.canonical_path

    @property
    def canonical_url(self) -> str:
        return self.route.canonical_url


@dataclass(frozen=True)
class TagTaxonomyResult:
    tags: tuple[Tag, ...] = field(default_factory=tuple)
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)
