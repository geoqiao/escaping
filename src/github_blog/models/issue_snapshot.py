"""Immutable in-memory Issue snapshot for the Site Compiler.

This is a build-time, in-memory value produced by the GitHub adapter. It is not
persisted and is not a second content authority: the GitHub Issue remains the
sole authoritative representation. Only fields needed by the compiler are
captured, so no PyGithub object crosses this seam.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class IssueSnapshot:
    """Immutable snapshot of a GitHub Issue's compiler-relevant fields.

    Fields mirror the authoritative inputs of the Issue Content Contract:
    number (content id + comment thread), title, author login, the raw body
    (front matter included; parsing is downstream), label names (type,
    publication, and tags are derivable), the native Issue timestamps, and
    whether the item is a Pull Request (recorded so the compiler can exclude
    PRs during selection).
    """

    number: int
    title: str
    author: str
    body: str
    labels: tuple[str, ...]
    created_at: datetime
    updated_at: datetime
    is_pull_request: bool
