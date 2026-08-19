from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..build_result import Diagnostic
from ..routes import Route


@dataclass(frozen=True)
class AtomEntry:
    id: str
    title: str
    link: str
    summary: str
    published: datetime
    updated: datetime
    content_html: str | None


@dataclass(frozen=True)
class AtomFeed:
    """Atom entries and timestamp carrying one complete registered Route."""

    route: Route
    updated: datetime
    entries: tuple[AtomEntry, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AtomFeedResult:
    feed: AtomFeed
    diagnostics: tuple[Diagnostic, ...] = field(default_factory=tuple)
