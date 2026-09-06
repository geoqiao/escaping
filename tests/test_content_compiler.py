from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from escaping.config import Settings
from escaping.content_compiler import ContentCompiler
from escaping.models.content import ContentCompilationResult
from escaping.models.issue_snapshot import IssueSnapshot
from escaping.routes import RouteRegistry

_NOW = datetime(2026, 1, 10, tzinfo=UTC)


def _settings(about_number: int = 10) -> Settings:
    return Settings.model_validate(
        {
            "github": {"repo": "geoqiao/site", "allowed_authors": ["geoqiao"]},
            "site": {
                "title": "geoqiao",
                "author": "geoqiao",
                "url": "https://geoqiao.me/",
            },
            "profile": {"avatar": "/avatar.png", "bio": "Builder"},
            "about": {"issue_number": about_number},
            "security": {"token_env": "TEST_TOKEN"},
        }
    )


def _compiler(about_number: int = 10) -> ContentCompiler:
    settings = _settings(about_number)
    return ContentCompiler(
        settings, route_registry=RouteRegistry(str(settings.site.url))
    )


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


def _codes(result: ContentCompilationResult) -> set[str]:
    return {d.code for d in result.diagnostics if d.severity == "error"}


@pytest.mark.parametrize("allowed_author", ["geoqiao", " \tGeoQiao\n"])
def test_compiles_blog_idea_and_configured_about_once(allowed_author: str) -> None:
    settings = Settings.model_validate(
        {
            **_settings().model_dump(),
            "github": {"repo": "geoqiao/site", "allowed_authors": [allowed_author]},
        }
    )
    result = ContentCompiler(
        settings, route_registry=RouteRegistry(str(settings.site.url))
    ).compile(
        [
            _snapshot(1, "blog"),
            _snapshot(2, "idea"),
            _snapshot(10, "about"),
            _snapshot(21, "blog", author="other"),
        ]
    )

    assert not result.has_errors
    assert [post.issue_number for post in result.blogs] == [1]
    assert result.blogs[0].canonical_path == "/blog/test-post/"
    assert result.ideas[0].canonical_path == "/ideas/2/"
    assert result.about is not None and result.about.canonical_path == "/about/"
    assert "description:" not in result.ideas[0].body_html
    assert "<script" not in result.ideas[0].body_html


def test_ideas_forbid_slug_sort_and_keep_tags_outside_blog_taxonomy() -> None:
    older = _NOW.replace(day=8)
    result = _compiler().compile(
        [
            _snapshot(2, "idea", labels=("tag:tools",), created_at=older),
            _snapshot(3, "idea", labels=("tag:notes",)),
            _snapshot(4, "blog", labels=("tag:python",)),
            _snapshot(10, "about"),
        ]
    )
    assert not result.has_errors
    assert [idea.issue_number for idea in result.ideas] == [3, 2]
    assert [tag.name for tag in result.ideas[1].tags] == ["tools"]
    assert {tag.name for blog in result.blogs for tag in blog.tags} == {"python"}

    invalid = _compiler().compile(
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
    "configured,other,expected",
    [
        (_snapshot(10, "about", published=False), None, "ABOUT_UNPUBLISHED"),
        (_snapshot(10, "about", author="other"), None, "ABOUT_UNAUTHORIZED"),
        (_snapshot(10, "about", is_pr=True), None, "ABOUT_IS_PULL_REQUEST"),
        (_snapshot(10, "idea"), None, "ABOUT_TYPE_INVALID"),
        (_snapshot(10, "about"), _snapshot(11, "about"), "ABOUT_DUPLICATE"),
    ],
)
def test_about_failure_matrix(
    configured: IssueSnapshot, other: IssueSnapshot | None, expected: str
) -> None:
    snapshots = [configured] + ([other] if other is not None else [])
    result = _compiler().compile(snapshots)
    assert expected in _codes(result)
    assert result.about is None


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
    result = _compiler().compile([snapshot, _snapshot(10, "about")])
    assert not result.has_errors, result.diagnostics
    post = result.blogs[0]
    assert (post.slug, post.description, post.created_date) == expected
    assert post.body_html == "<p>Writing should be simple.</p>\n"
    assert post.published_at == created and post.updated_at == created
    renamed = _compiler().compile(
        [replace(snapshot, title="Changed title"), _snapshot(10, "about")]
    )
    assert renamed.blogs[0].canonical_path == post.canonical_path


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
    ],
)
def test_description_uses_only_sanitized_visible_body_text(
    body: str, expected: str
) -> None:
    result = _compiler().compile(
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
def test_explicit_invalid_metadata_fails_the_entire_batch(
    metadata: str, code: str
) -> None:
    result = _compiler().compile(
        [
            _snapshot(128, "blog", metadata=metadata),
            _snapshot(1, "blog"),
            _snapshot(10, "about"),
        ]
    )
    assert code in _codes(result)
    assert any(d.code == code and d.issue_number == 128 for d in result.diagnostics)
    assert not result.blogs and not result.ideas and result.about is None


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
    good = _compiler().compile([plain, *ignored, _snapshot(10, "about")])
    assert not good.has_errors, good.diagnostics
    assert [p.issue_number for p in good.blogs] == [128]
    assert [(d.code, d.issue_number) for d in good.diagnostics] == [
        ("UNAUTHORIZED_AUTHOR", 4)
    ]
    removed = _compiler().compile(
        [replace(plain, labels=("type:blog",)), _snapshot(10, "about")]
    )
    assert not removed.has_errors and not removed.blogs
    bad = _compiler().compile(
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
    assert not bad.blogs and bad.about is None


def test_default_and_explicit_slugs_share_registry_and_collision_checks() -> None:
    routes = RouteRegistry(str(_settings().site.url))
    default = replace(_snapshot(128, "blog"), body="Body.")
    registered = ContentCompiler(_settings(), route_registry=routes).compile(
        [default, _snapshot(10, "about")]
    )
    assert not registered.has_errors
    assert registered.blogs[0].route is routes.route("blog-detail-128")
    collision = _compiler().compile(
        [
            default,
            _snapshot(129, "blog", metadata='slug: "128"'),
            _snapshot(10, "about"),
        ]
    )
    assert "SLUG_DUPLICATE" in _codes(collision)
    assert not collision.blogs


@pytest.mark.parametrize("kind,number", [("idea", 2), ("about", 10)])
def test_idea_about_defaults_never_allow_a_slug(kind: str, number: int) -> None:
    supporting = [] if kind == "about" else [_snapshot(10, "about")]
    result = _compiler().compile(
        [replace(_snapshot(number, kind), body="Body."), *supporting]
    )
    assert not result.has_errors, result.diagnostics
    page = result.about if kind == "about" else result.ideas[0]
    assert page is not None and page.description == "Body."
    if kind == "idea":
        assert result.ideas[0].created_date == "2026-01-10"
    for value in ("null", '""', "forbidden"):
        bad = _compiler().compile(
            [_snapshot(number, kind, metadata=f"slug: {value}"), *supporting]
        )
        assert "SLUG_FORBIDDEN" in _codes(bad)


def test_missing_about_and_about_tags_fail() -> None:
    missing = _compiler().compile([_snapshot(1, "blog")])
    assert "ABOUT_MISSING" in _codes(missing)

    tagged = _compiler().compile([_snapshot(10, "about", labels=("tag:profile",))])
    assert "ABOUT_TAG_FORBIDDEN" in _codes(tagged)
