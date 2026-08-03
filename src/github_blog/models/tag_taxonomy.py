from __future__ import annotations

from dataclasses import dataclass, field

from ..build_result import Diagnostic
from ..routes import Route
from .blog_post import BlogTag


@dataclass(frozen=True)
class TagSummary:
    name: str
    count: int
    route: Route


@dataclass(frozen=True)
class TagArchiveEntry:
    issue_number: int
    title: str
    created_date: str
    detail_path: str
    tags: tuple[BlogTag, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TagsIndex:
    route: Route
    tags: tuple[TagSummary, ...] = field(default_factory=tuple)

    @property
    def canonical_url(self) -> str:
        return self.route.canonical_url


@dataclass(frozen=True)
class TagArchive:
    route: Route
    tag_name: str
    index_route: Route
    entries: tuple[TagArchiveEntry, ...] = field(default_factory=tuple)

    @property
    def canonical_url(self) -> str:
        return self.route.canonical_url


@dataclass(frozen=True)
class TagTaxonomyResult:
    index: TagsIndex
    archives: tuple[TagArchive, ...] = field(default_factory=tuple)
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)

    @property
    def has_errors(self) -> bool:
        return any(d.severity == "error" for d in self.diagnostics)
