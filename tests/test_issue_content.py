"""Issue Content: the entries both outputs start from, and what they must not know.

Selection and content rules are exercised through the site's compiler in
``test_content_compiler.py``; these tests own what only the shared core has.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from escaping_site.issue_content import ContentRules, compile_issues
from escaping_site.models.issue_snapshot import IssueSnapshot

_RULES = ContentRules(allowed_authors=("alice",))


def _issue(number: int, body: str, *labels: str) -> IssueSnapshot:
    return IssueSnapshot(
        number=number,
        title="Title",
        author="alice",
        body=body,
        labels=("published", *(labels or ("type:blog",))),
        created_at=datetime(2026, 1, 1, 23, 30, tzinfo=UTC),
        updated_at=datetime(2026, 3, 5, 1, 0, tzinfo=UTC),
        is_pull_request=False,
    )


@pytest.mark.parametrize(
    ("front_matter", "expected"),
    [
        # Left out: not revised, whatever happened to the Issue since.
        ("", ("2026-01-01", "2026-01-01")),
        # Written: the day the author revised it.
        ('update_date: "2026-02-10"', ("2026-01-01", "2026-02-10")),
        ('created_date: "2025-06-01"\nupdate_date: "2025-06-01"', ("2025-06-01",) * 2),
        ('created_date: "2026-04-01"', ("2026-04-01", "2026-04-01")),
    ],
)
def test_update_date_is_the_authors_or_the_creation_date(
    front_matter: str, expected: tuple[str, str]
) -> None:
    body = f"---\n{front_matter}\n---\nBody." if front_matter else "Body."

    result = compile_issues(_RULES, [_issue(1, body), _issue(2, body, "type:idea")])

    assert not result.diagnostics
    for entry in (*result.blogs, *result.ideas):
        assert (entry.created_date, entry.update_date) == expected


@pytest.mark.parametrize(
    ("front_matter", "code"),
    [
        ("update_date: 2026-02-10", "UPDATE_DATE_INVALID"),  # not quoted
        ('update_date: "2026-02-30"', "UPDATE_DATE_INVALID"),
        ('update_date: "2025-12-31"', "UPDATE_DATE_BEFORE_CREATED"),
        (
            'created_date: "2026-02-01"\nupdate_date: "2026-01-15"',
            "UPDATE_DATE_BEFORE_CREATED",
        ),
    ],
)
def test_a_wrong_update_date_skips_the_issue(front_matter: str, code: str) -> None:
    result = compile_issues(_RULES, [_issue(1, f"---\n{front_matter}\n---\nBody.")])

    assert [(d.code, d.field) for d in result.diagnostics] == [(code, "update_date")]
    assert result.skipped == (1,) and not result.blogs and not result.has_errors


def test_every_type_is_content_unless_the_caller_has_no_place_for_it() -> None:
    issues = [
        _issue(1, "Body."),
        _issue(2, "Body.", "type:idea"),
        _issue(3, "Body.", "type:about"),
    ]

    everything = compile_issues(_RULES, issues)
    assert [e.issue_number for e in everything.blogs] == [1]
    assert [e.issue_number for e in everything.ideas] == [2]
    assert everything.about is not None and everything.about.issue_number == 3
    assert everything.blogs[0].slug == "1" and everything.ideas[0].slug == ""

    without = compile_issues(
        replace(_RULES, off={"idea": "this site has none"}), issues
    )
    assert not without.ideas and not without.skipped
    assert [(d.severity, d.code, d.message) for d in without.diagnostics] == [
        (
            "warning",
            "PAGE_OFF",
            "Issue #2: is type:idea but this site has none; it is not published",
        )
    ]


def test_an_export_loads_nothing_that_builds_a_site() -> None:
    """The dependency runs one way: a build uses the content, never the reverse."""
    script = (
        "import sys, escaping_site.content_export\n"
        "site = ('content_compiler', 'site_compiler', 'site_builder', 'theme',"
        " 'projects', 'search', 'artifact_validation',"
        " 'services.render_service', 'models.site')\n"
        "loaded = [m for m in site if f'escaping_site.{m}' in sys.modules]\n"
        "loaded += [m for m in ('jinja2',) if m in sys.modules]\n"
        "print(','.join(loaded))"
    )
    done = subprocess.run(  # noqa: S603 - this interpreter, a fixed script
        [sys.executable, "-c", script], check=True, capture_output=True, text=True
    )
    assert done.stdout.strip() == ""
