"""Issue Content: which Issues are published and what each value resolves to."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from escaping_site.config import GithubConfig
from escaping_site.content_validation import tag_key
from escaping_site.issue_content import ContentRules, IssueContent, compile_issues
from escaping_site.models.issue_snapshot import IssueSnapshot

_NOW = datetime(2026, 1, 10, tzinfo=UTC)


def _compile(
    snapshots: list[IssueSnapshot],
    *,
    about: int | None = 10,
    authors: tuple[str, ...] = ("geoqiao",),
) -> IssueContent:
    return compile_issues(ContentRules(authors, about), snapshots)


def _snapshot(
    number: int,
    content_type: str,
    *,
    title: str = "Title",
    metadata: str | None = None,
    labels: tuple[str, ...] = (),
    author: str = "geoqiao",
    published: bool = True,
    is_pr: bool = False,
    created_at: datetime = _NOW,
) -> IssueSnapshot:
    if metadata is None:
        slug = "slug: test-post\n" if content_type == "blog" else ""
        metadata = (
            f'{slug}description: A useful description.\ncreated_date: "2026-01-02"'
        )
    all_labels = (f"type:{content_type}", *labels)
    if published:
        all_labels = (*all_labels, "published")
    return IssueSnapshot(
        number=number,
        title=title,
        author=author,
        body=f"---\n{metadata}\n---\n\nVisible **body**.<script>bad()</script>",
        labels=all_labels,
        created_at=created_at,
        updated_at=created_at,
        is_pull_request=is_pr,
    )


def _codes(result: IssueContent) -> set[str]:
    return {d.code for d in result.diagnostics if d.severity == "error"}


@pytest.mark.parametrize("allowed_author", ["geoqiao", " \tGeoQiao\n"])
def test_compiles_blog_idea_and_configured_about_once(allowed_author: str) -> None:
    result = _compile(
        [
            _snapshot(1, "blog"),
            _snapshot(2, "idea"),
            _snapshot(10, "about"),
            _snapshot(21, "blog", author="other"),
        ],
        authors=tuple(
            GithubConfig(
                repo="geoqiao/site", allowed_authors=[allowed_author]
            ).allowed_authors
        ),
    )

    assert not result.has_errors
    assert [post.issue_number for post in result.blogs] == [1]
    assert result.blogs[0].slug == "test-post"
    assert [idea.issue_number for idea in result.ideas] == [2]
    assert result.about is not None and result.about.issue_number == 10
    assert "description:" not in result.ideas[0].body_html
    assert "<script" not in result.ideas[0].body_html


@pytest.mark.parametrize("kind", ["blog", "idea"])
@pytest.mark.parametrize(
    ("authored", "canonical"),
    [("٢٠٢٦-01-01", "2026-01-01"), ("0001-01-01", "0001-01-01")],
)
def test_authored_calendar_dates_compile_to_ascii_without_changing_issue_time(
    kind: str, authored: str, canonical: str
) -> None:
    result = _compile(
        [
            _snapshot(1, kind, metadata=f'created_date: "{authored}"'),
            _snapshot(10, "about", metadata=f'created_date: "{authored}"'),
        ]
    )
    assert not result.has_errors
    item = result.blogs[0] if kind == "blog" else result.ideas[0]
    assert item.created_date == canonical
    assert item.published_at == item.updated_at == _NOW


def test_blog_posts_come_out_newest_first() -> None:
    older = _NOW.replace(day=8)
    result = _compile(
        [
            _snapshot(2, "blog", metadata="slug: two"),
            _snapshot(5, "blog", metadata="slug: five", created_at=older),
            _snapshot(3, "blog", metadata="slug: three"),
            _snapshot(10, "about"),
        ]
    )
    assert not result.has_errors
    # At the same time, the higher Issue number is the newer post.
    assert [post.issue_number for post in result.blogs] == [3, 2, 5]


def test_ideas_forbid_slug_sort_and_keep_tags_outside_blog_taxonomy() -> None:
    older = _NOW.replace(day=8)
    result = _compile(
        [
            _snapshot(2, "idea", labels=("tag:tools",), created_at=older),
            _snapshot(3, "idea", labels=("tag:notes",)),
            _snapshot(4, "blog", labels=("tag:python",)),
            _snapshot(10, "about"),
        ]
    )
    assert not result.has_errors
    assert [idea.issue_number for idea in result.ideas] == [3, 2]
    assert result.ideas[1].tags == ("tools",)
    assert {tag for blog in result.blogs for tag in blog.tags} == {"python"}

    invalid = _compile(
        [
            _snapshot(
                2,
                "idea",
                metadata='slug: forbidden\ndescription: D.\ncreated_date: "2026-01-02"',
            ),
            _snapshot(10, "about"),
        ]
    )
    assert "SLUG_FORBIDDEN" in _codes(invalid)


@pytest.mark.parametrize(
    "configured,expected",
    [
        (_snapshot(10, "about", published=False), "ABOUT_UNPUBLISHED"),
        (_snapshot(10, "about", author="other"), "ABOUT_UNAUTHORIZED"),
        (_snapshot(10, "about", is_pr=True), "ABOUT_IS_PULL_REQUEST"),
        (_snapshot(10, "idea"), "ABOUT_TYPE_INVALID"),
    ],
)
def test_configured_about_failures_stop_the_build(
    configured: IssueSnapshot, expected: str
) -> None:
    result = _compile([configured, _snapshot(1, "blog")])
    assert expected in _codes(result)
    assert result.has_errors and result.about is None and not result.skipped


def test_other_about_issues_are_skipped_when_one_is_configured() -> None:
    result = _compile(
        [_snapshot(11, "about"), _snapshot(10, "about"), _snapshot(1, "blog")]
    )
    assert not result.has_errors, result.diagnostics
    assert result.about is not None and result.about.issue_number == 10
    assert result.skipped == (11,)
    assert [(d.code, d.issue_number) for d in result.diagnostics] == [
        ("ABOUT_NOT_SELECTED", 11)
    ]


@pytest.mark.parametrize(
    "metadata,expected",
    [
        (None, ("128", "Writing should be simple.", "2026-01-01")),
        ("", ("128", "Writing should be simple.", "2026-01-01")),
        ("{}", ("128", "Writing should be simple.", "2026-01-01")),
        ("slug: chosen", ("chosen", "Writing should be simple.", "2026-01-01")),
        (
            "description: An authored summary.",
            ("128", "An authored summary.", "2026-01-01"),
        ),
        (
            'created_date: "2020-02-29"',
            ("128", "Writing should be simple.", "2020-02-29"),
        ),
        (
            'slug: original\ndescription: Original summary.\ncreated_date: "2020-02-29"',
            ("original", "Original summary.", "2020-02-29"),
        ),
    ],
)
def test_missing_metadata_defaults_and_independent_overrides(
    metadata: str | None, expected: tuple[str, str, str]
) -> None:
    created = datetime.fromisoformat("2026-01-02T00:30:00+02:00")
    body = "Writing should be simple."
    if metadata is not None:
        body = f"---\n{metadata}\n---\n\n{body}"
    snapshot = replace(_snapshot(128, "blog", created_at=created), body=body)
    result = _compile([snapshot, _snapshot(10, "about")])
    assert not result.has_errors, result.diagnostics
    post = result.blogs[0]
    assert (post.slug, post.description, post.created_date) == expected
    assert post.body_html == "<p>Writing should be simple.</p>\n"
    assert post.published_at == created and post.updated_at == created
    renamed = _compile(
        [replace(snapshot, title="Changed title"), _snapshot(10, "about")]
    )
    assert renamed.blogs[0].slug == post.slug


@pytest.mark.parametrize(
    "body,expected",
    [
        ("Hel**lo** &amp; [friends](https://example.org).", "Hello & friends."),
        ("# Heading\n\nBody.", "Heading Body."),
        (
            "<div>one</div><p>two<br>three</p><ul><li>four</li><li>five</li></ul>",
            "one two three four five",
        ),
        ("<table><tr><td>one</td><td>two</td></tr></table>", "one two"),
        ("  中文🙂" * 30, ("中文🙂 " * 30).strip()[:50]),
        ("e\u0301" * 30, "e\u0301" * 25),
        ("Use `<button>`.", "Use <button>."),
        ("```html\n<button>&amp;</button>\n```", "<button>&amp;</button>"),
        ("![Picture](https://example.org/p.png)", ""),
        (
            'Before<img src="https://example.org/p.png" alt="hidden">After',
            "BeforeAfter",
        ),
        (
            "<div>Safe<button>hidden</button> text.</div>",
            "Safe text.",
        ),
        (
            "slug: is a word.\n\n---\n\n```yaml\ndescription: literal\n```",
            "slug: is a word. description: literal",
        ),
        (
            "| a | b |\n|---|---|\n\n```mermaid\ngraph TD; A-->B;\n```\nAfter.",
            "a b After.",
        ),
    ],
)
def test_description_uses_only_sanitized_visible_body_text(
    body: str, expected: str
) -> None:
    result = _compile(
        [replace(_snapshot(128, "blog"), body=body), _snapshot(10, "about")]
    )
    assert not result.has_errors, result.diagnostics
    assert result.blogs[0].description == expected


@pytest.mark.parametrize(
    "metadata,code",
    [
        *[
            (f"{field}: {value}", f"{field.upper()}_INVALID")
            for field in ("slug", "description", "created_date")
            for value in ("null", '""', '"   "', "42", "[]")
        ],
        ("slug: Bad-Slug", "SLUG_INVALID"),
        ("slug: " + "x" * 81, "SLUG_INVALID"),
        ("slug: page", "SLUG_RESERVED"),
        ("description: '<button>'", "DESCRIPTION_INVALID"),
        ('description: "line\\nline"', "DESCRIPTION_INVALID"),
        ("description: " + "x" * 301, "DESCRIPTION_TOO_LONG"),
        ("created_date: 2026-01-01", "CREATED_DATE_INVALID"),
        ('created_date: "2025-02-29"', "CREATED_DATE_INVALID"),
        ("created_date: !!str 2026-01-01", "CREATED_DATE_INVALID"),
        ("unknown: value", "FRONT_MATTER_UNKNOWN_FIELD"),
    ],
)
def test_explicit_invalid_metadata_skips_only_that_issue(
    metadata: str, code: str
) -> None:
    result = _compile(
        [
            _snapshot(128, "blog", metadata=metadata),
            _snapshot(1, "blog"),
            _snapshot(10, "about"),
        ]
    )
    assert code in _codes(result)
    assert any(d.code == code and d.issue_number == 128 for d in result.diagnostics)
    assert not result.has_errors and result.skipped == (128,)
    assert [post.issue_number for post in result.blogs] == [1]
    assert result.about is not None


@pytest.mark.parametrize(
    "field,snapshot",
    [
        ("title", _snapshot(128, "blog", title="Bad\x01Title")),
        ("body", replace(_snapshot(128, "blog"), body="Bad \x01 char.")),
        ("body", replace(_snapshot(128, "blog"), body="Bad ￿ char.")),
        ("description", _snapshot(128, "blog", metadata='description: "A\\uFFFE"')),
    ],
)
def test_a_character_the_feed_cannot_hold_skips_only_that_blog(
    field: str, snapshot: IssueSnapshot
) -> None:
    result = _compile([snapshot, _snapshot(1, "blog"), _snapshot(10, "about")])
    [error] = [d for d in result.diagnostics if d.severity == "error"]
    assert (error.code, error.issue_number, error.field) == (
        "CHARACTER_INVALID",
        128,
        field,
    )
    assert "Bad" not in error.message
    assert not result.has_errors and result.skipped == (128,)
    assert [post.issue_number for post in result.blogs] == [1]


def test_defaults_keep_publication_gates_and_collect_published_errors() -> None:
    plain = replace(
        _snapshot(128, "blog"),
        body="Visible body.",
        author="GeoQiao",
        labels=("TYPE:BLOG", "PUBLISHED"),
    )
    ignored = [
        replace(_snapshot(2, "blog", published=False), body="---\nbroken: ["),
        replace(_snapshot(3, "blog", published=False), body="---", labels=()),
        replace(_snapshot(4, "blog", author="other"), body="---"),
        replace(_snapshot(5, "blog", is_pr=True), body="---"),
    ]
    good = _compile([plain, *ignored, _snapshot(10, "about")])
    assert not good.has_errors, good.diagnostics
    assert [p.issue_number for p in good.blogs] == [128]
    assert [(d.code, d.issue_number) for d in good.diagnostics] == [
        ("UNAUTHORIZED_AUTHOR", 4)
    ]
    removed = _compile([replace(plain, labels=("type:blog",)), _snapshot(10, "about")])
    assert not removed.has_errors and not removed.blogs
    bad = _compile(
        [
            plain,
            _snapshot(10, "about"),
            replace(plain, number=20, labels=("published",)),
            replace(plain, number=21, labels=("published", "type:blog", "type:idea")),
            replace(plain, number=22, labels=("published", "type:unknown")),
            replace(plain, number=23, body="---\nbroken: ["),
        ]
    )
    assert _codes(bad) == {
        "TYPE_LABEL_MISSING",
        "TYPE_LABEL_MULTIPLE",
        "TYPE_LABEL_UNKNOWN",
        "FRONT_MATTER_UNCLOSED",
    }
    assert not bad.has_errors and bad.skipped == (20, 21, 22, 23)
    assert [p.issue_number for p in bad.blogs] == [128]
    assert bad.about is not None


def test_oldest_issue_keeps_a_contested_slug() -> None:
    default = replace(_snapshot(128, "blog"), body="Body.")
    registered = _compile([default, _snapshot(10, "about")])
    assert not registered.has_errors
    assert registered.blogs[0].slug == "128"
    # Input order does not matter: the lower Issue number owns the slug.
    collision = _compile(
        [
            _snapshot(129, "blog", metadata='slug: "128"'),
            default,
            _snapshot(10, "about"),
        ]
    )
    assert not collision.has_errors and collision.skipped == (129,)
    assert [p.issue_number for p in collision.blogs] == [128]
    duplicate = next(d for d in collision.diagnostics if d.code == "SLUG_DUPLICATE")
    assert duplicate.issue_number == 129 and "#128" in duplicate.message


def test_unicode_tags_keep_display_names_and_share_keys() -> None:
    result = _compile(
        [
            _snapshot(
                1,
                "blog",
                labels=(
                    "tag:Machine Learning",
                    "TAG:machine_learning",
                    "tag:示例 标签",
                ),
            ),
            _snapshot(2, "blog", metadata="slug: other", labels=("tag:C++",)),
            _snapshot(10, "about"),
        ]
    )
    assert not result.has_errors and result.skipped == (2,)
    assert "TAG_INVALID" in _codes(result)
    tags = result.blogs[0].tags
    assert [(tag, tag_key(tag)) for tag in tags] == [
        ("Machine Learning", "machine-learning"),
        ("示例 标签", "示例-标签"),
    ]


@pytest.mark.parametrize("kind,number", [("idea", 2), ("about", 10)])
def test_idea_about_defaults_never_allow_a_slug(kind: str, number: int) -> None:
    supporting = [] if kind == "about" else [_snapshot(10, "about")]
    result = _compile([replace(_snapshot(number, kind), body="Body."), *supporting])
    assert not result.has_errors, result.diagnostics
    page = result.about if kind == "about" else result.ideas[0]
    assert page is not None and page.description == "Body."
    if kind == "idea":
        assert result.ideas[0].created_date == "2026-01-10"
    for value in ("null", '""', "forbidden"):
        bad = _compile(
            [_snapshot(number, kind, metadata=f"slug: {value}"), *supporting]
        )
        assert "SLUG_FORBIDDEN" in _codes(bad)


def test_missing_about_and_about_tags_fail() -> None:
    missing = _compile([_snapshot(1, "blog")])
    assert "ABOUT_MISSING" in _codes(missing) and missing.has_errors

    tagged = _compile([_snapshot(10, "about", labels=("tag:profile",))])
    assert "ABOUT_TAG_FORBIDDEN" in _codes(tagged) and tagged.has_errors


def test_about_discovery_requires_a_unique_valid_published_candidate() -> None:
    def discover(snapshots: list[IssueSnapshot]) -> IssueContent:
        return _compile(snapshots, about=None)

    empty = discover(
        [_snapshot(4, "about", published=False), _snapshot(5, "about", author="other")]
    )
    assert not empty.has_errors and empty.about is None
    discovered = discover([_snapshot(42, "about")])
    assert not discovered.has_errors and discovered.about is not None
    assert discovered.about.issue_number == 42
    duplicate = discover([_snapshot(43, "about"), _snapshot(42, "about")])
    assert "ABOUT_DUPLICATE" in _codes(duplicate)
    assert not duplicate.has_errors and duplicate.skipped == (43,)
    assert duplicate.about is not None and duplicate.about.issue_number == 42
    invalid = discover([_snapshot(42, "about", metadata="slug: forbidden")])
    assert "SLUG_FORBIDDEN" in _codes(invalid) and invalid.about is None
    assert not invalid.has_errors and invalid.skipped == (42,)


def _compiled_body(markdown: str) -> str:
    result = _compile(
        [replace(_snapshot(1, "blog"), body=markdown), _snapshot(10, "about")]
    )
    assert not result.has_errors, result.diagnostics
    return result.blogs[0].body_html


def test_task_list_keeps_done_and_open_state() -> None:
    # The sanitizer drops <input>, so the state is shown as text.
    assert _compiled_body("- [x] shipped\n- [ ] pending\n") == (
        "<ul>\n<li>☑ shipped</li>\n<li>☐ pending</li>\n</ul>\n"
    )
