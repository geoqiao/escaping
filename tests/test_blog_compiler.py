"""Tests for the Blog detail compiler (Ticket 04 primary seam).

IssueSnapshot + content policy -> BlogCompilationResult with compiled BlogPost
values and accumulated diagnostics.  Covers published Blog selection, front-matter
validation, GFM rendering + sanitization, error accumulation, NFC/case-insensitive
comparisons, fullmatch kebab validation, and route output.

Direct sanitizer attack matrix lives in test_html_sanitizer.py; this file keeps
one compiler -> two themes tracer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import HttpUrl

from github_blog.blog_compiler import BlogCompiler
from github_blog.config import (
    AboutConfig,
    GithubConfig,
    SecurityConfig,
    Settings,
    SiteConfig,
)
from github_blog.models.blog_post import BlogCompilationResult, BlogTag
from github_blog.models.issue_snapshot import IssueSnapshot

_DEFAULT_CREATED = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)
_DEFAULT_UPDATED = datetime(2026, 1, 11, 8, 30, tzinfo=timezone.utc)

_VALID_BODY = (
    "---\nslug: my-first-post\ndescription: A test post about things.\n"
    'created_date: "2026-01-05"\n---\n\nHello **world**.\n'
)


def _snap(
    number: int = 1,
    *,
    title: str = "Test Post",
    body: str = _VALID_BODY,
    author: str = "alice",
    labels: tuple[str, ...] = ("type:blog", "published"),
    created_at: datetime = _DEFAULT_CREATED,
    updated_at: datetime = _DEFAULT_UPDATED,
    is_pr: bool = False,
) -> IssueSnapshot:
    return IssueSnapshot(
        number, title, author, body, labels, created_at, updated_at, is_pr
    )


def _settings(allowed: list[str] | None = None) -> Settings:
    return Settings(
        github=GithubConfig(repo="user/repo", allowed_authors=allowed or ["alice"]),
        site=SiteConfig(title="T", url=HttpUrl("https://example.com/"), author="A"),
        about=AboutConfig(issue_number=1),
        security=SecurityConfig(token_env="G_T"),  # noqa: S106
    )


def _compile(
    snaps: list[IssueSnapshot], settings: Settings | None = None
) -> BlogCompilationResult:
    return BlogCompiler(settings or _settings()).compile(snaps)


def _err_codes(
    result: BlogCompilationResult, issue_number: int | None = None
) -> set[str]:
    return {
        d.code
        for d in result.diagnostics
        if d.severity == "error"
        and (issue_number is None or d.issue_number == issue_number)
    }


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def test_pr_excluded() -> None:
    assert _compile([_snap(is_pr=True)]).posts == ()
    assert _compile([_snap(is_pr=True, labels=("type:blog", "published"))]).posts == ()


def test_unauthorized_author() -> None:
    # Unauthorized: warns, body not parsed (no front-matter errors)
    r = _compile([_snap(author="bob", body="no front matter")])
    assert r.posts == () and not r.has_errors
    assert len(r.diagnostics) == 1 and r.diagnostics[0].code == "UNAUTHORIZED_AUTHOR"
    # Case-insensitive
    assert len(_compile([_snap(author="Alice")]).posts) == 1
    # NFC: composed Á (U+00C1) matches decomposed A + combining acute (U+0041 + U+0301)
    composed = "\u00c1lice"
    decomposed = "A\u0301lice"
    assert (
        len(
            BlogCompiler(_settings(allowed=[composed]))
            .compile([_snap(author=decomposed)])
            .posts
        )
        == 1
    )


def test_unpublished_ignored() -> None:
    # No parsing for unpublished
    r = _compile([_snap(labels=("type:blog",), body="totally invalid")])
    assert r.posts == () and len(r.diagnostics) == 0
    # Malformed body still no diagnostics
    r2 = _compile(
        [_snap(labels=("type:blog",), body="---\nslug: x\nslug: y\n---\nbody")]
    )
    assert len(r2.diagnostics) == 0


@pytest.mark.parametrize(
    "labels, expect_error_codes, expect_posts",
    [
        (("published",), {"TYPE_LABEL_MISSING"}, 0),
        (("type:blog", "type:idea", "published"), {"TYPE_LABEL_MULTIPLE"}, 0),
        (("type:foo", "published"), {"TYPE_LABEL_UNKNOWN"}, 0),
        (
            ("type:blog", "type:foo", "published"),
            {"TYPE_LABEL_MULTIPLE", "TYPE_LABEL_UNKNOWN"},
            0,
        ),
        (
            ("type:foo", "type:bar", "published"),
            {"TYPE_LABEL_MULTIPLE", "TYPE_LABEL_UNKNOWN"},
            0,
        ),
        (("type:idea", "published"), set(), 0),
        (("type:about", "published"), set(), 0),
        (("Type:Blog", "Published"), set(), 1),
    ],
    ids=[
        "missing",
        "multiple",
        "unknown",
        "multi+unknown",
        "two-unknown",
        "idea",
        "about",
        "case-insensitive",
    ],
)
def test_type_label_cardinality(
    labels: tuple[str, ...], expect_error_codes: set[str], expect_posts: int
) -> None:
    r = _compile([_snap(labels=labels)])
    assert _err_codes(r) == expect_error_codes
    assert len(r.posts) == expect_posts


# ---------------------------------------------------------------------------
# Front-matter validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body, expect_code",
    [
        ("No front matter here.", "FRONT_MATTER_MISSING"),
        ("---\nslug: x\nbody without close", "FRONT_MATTER_UNCLOSED"),
        ("---\n- item1\n- item2\n---\nbody", "FRONT_MATTER_NOT_MAPPING"),
        ("---\nslug: a\nslug: b\n---\nbody", "FRONT_MATTER_DUPLICATE_KEY"),
        (
            '---\nslug: x\ndescription: d\ncreated_date: "2026-01-01"\nfoo: bar\n---\nbody',
            "FRONT_MATTER_UNKNOWN_FIELD",
        ),
    ],
    ids=["missing", "unclosed", "not-mapping", "duplicate", "unknown-field"],
)
def test_front_matter_validation(body: str, expect_code: str) -> None:
    r = _compile([_snap(body=body)])
    assert r.has_errors
    assert expect_code in _err_codes(r)


# ---------------------------------------------------------------------------
# Field validation: slug
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body, expect_code",
    [
        ('---\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody', "SLUG_MISSING"),
        (
            '---\nslug: Invalid Slug!\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody',
            "SLUG_INVALID",
        ),
        (
            f'---\nslug: {"a" * 81}\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody',
            "SLUG_INVALID",
        ),
    ],
    ids=["missing", "invalid-format", "too-long"],
)
def test_slug_validation_errors(body: str, expect_code: str) -> None:
    r = _compile([_snap(body=body)])
    assert expect_code in _err_codes(r)


def test_slug_valid_and_duplicate() -> None:
    body = '---\nslug: my-post\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody'
    r = _compile([_snap(body=body)])
    assert not r.has_errors and r.posts[0].slug == "my-post"
    # Duplicate
    r2 = _compile([_snap(number=1, body=body), _snap(number=2, body=body)])
    assert "SLUG_DUPLICATE" in _err_codes(r2)


# ---------------------------------------------------------------------------
# Field validation: description
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "desc_extra, expect_code",
    [
        ("", "DESCRIPTION_MISSING"),
        ('description: ""\n', "DESCRIPTION_INVALID"),
        ('description: "has\\ttab"\n', "DESCRIPTION_INVALID"),
        ('description: "has <tag>"\n', "DESCRIPTION_INVALID"),
        ('description: "line1\u2028line2"\n', "DESCRIPTION_INVALID"),
        ('description: "line1\u2029line2"\n', "DESCRIPTION_INVALID"),
        ('description: "has\\u0081char"\n', "DESCRIPTION_INVALID"),
        (f"description: {'x' * 301}\n", "DESCRIPTION_TOO_LONG"),
    ],
    ids=["missing", "empty", "tab", "angle", "line-sep", "para-sep", "c1", "too-long"],
)
def test_description_validation_errors(
    desc_extra: str, expect_code: str | None
) -> None:
    body = f'---\nslug: x\n{desc_extra}created_date: "2026-01-01"\n---\nbody'
    r = _compile([_snap(body=body)])
    assert r.has_errors
    if expect_code:
        assert expect_code in _err_codes(r)


def test_description_300_accepted() -> None:
    body = (
        f'---\nslug: x\ndescription: {"x" * 300}\ncreated_date: "2026-01-01"\n---\nbody'
    )
    assert not _compile([_snap(body=body)]).has_errors


# ---------------------------------------------------------------------------
# Field validation: created_date (format + quoting style)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "date_expr, expect_code",
    [
        ("---\nslug: x\ndescription: d\n---\nbody", "CREATED_DATE_MISSING"),
        (
            '---\nslug: x\ndescription: d\ncreated_date: "2026/01/01"\n---\nbody',
            "CREATED_DATE_INVALID",
        ),
        (
            '---\nslug: x\ndescription: d\ncreated_date: "2026-02-30"\n---\nbody',
            "CREATED_DATE_INVALID",
        ),
        (
            "---\nslug: x\ndescription: d\ncreated_date: 2026-01-01\n---\nbody",
            "CREATED_DATE_INVALID",
        ),
        (
            "---\nslug: x\ndescription: d\ncreated_date: !!str 2026-01-01\n---\nbody",
            "CREATED_DATE_INVALID",
        ),
        (
            "---\nslug: x\ndescription: d\ncreated_date: |-\n  2026-01-01\n---\nbody",
            "CREATED_DATE_INVALID",
        ),
        (
            "---\nslug: x\ndescription: d\ncreated_date: >-\n  2026-01-01\n---\nbody",
            "CREATED_DATE_INVALID",
        ),
    ],
    ids=[
        "missing",
        "bad-format",
        "bad-value",
        "plain",
        "explicit-str",
        "literal-block",
        "folded-block",
    ],
)
def test_created_date_validation_errors(date_expr: str, expect_code: str) -> None:
    r = _compile([_snap(body=date_expr)])
    assert expect_code in _err_codes(r)


@pytest.mark.parametrize(
    "date_expr",
    [
        'created_date: "2026-03-15"',
        "created_date: '2026-01-01'",
    ],
    ids=["double-quoted", "single-quoted"],
)
def test_created_date_quoted_accepted(date_expr: str) -> None:
    body = f"---\nslug: x\ndescription: d\n{date_expr}\n---\nbody"
    r = _compile([_snap(body=body)])
    assert not r.has_errors


# ---------------------------------------------------------------------------
# Title and body validation
# ---------------------------------------------------------------------------


def test_title_and_body_errors() -> None:
    # Empty title + valid body
    r = _compile([_snap(title="")])
    assert "TITLE_EMPTY" in _err_codes(r)
    # Empty body
    body = '---\nslug: x\ndescription: d\ncreated_date: "2026-01-01"\n---\n\n'
    assert "BODY_EMPTY" in _err_codes(_compile([_snap(body=body)]))
    # Whitespace-only body
    body_ws = '---\nslug: x\ndescription: d\ncreated_date: "2026-01-01"\n---\n   \n  \n'
    assert "BODY_EMPTY" in _err_codes(_compile([_snap(body=body_ws)]))


# ---------------------------------------------------------------------------
# Front-matter removal & sanitization
# ---------------------------------------------------------------------------


def test_front_matter_not_in_body_and_sanitized() -> None:
    body = (
        "---\nslug: secret-slug\ndescription: A post.\n"
        'created_date: "2026-01-01"\n---\n\n'
        "<script>alert(1)</script>\n\nVisible content."
    )
    r = _compile([_snap(body=body)])
    assert not r.has_errors
    html = r.posts[0].body_html
    assert "secret-slug" not in html
    assert "created_date" not in html
    assert "<script" not in html.lower()
    assert "Visible content." in html


# ---------------------------------------------------------------------------
# Tag validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "labels, expect_error, expected_tags",
    [
        (
            ("type:blog", "published", "tag:python", "tag:rust"),
            None,
            {"python", "rust"},
        ),
        (("type:blog", "published", "tag:Python_Web"), "TAG_INVALID", set()),
        (("type:blog", "published", f"tag:{'a' * 51}"), "TAG_INVALID", set()),
        (("type:blog", "published"), None, set()),
        (("Type:Blog", "Published", "Tag:Python"), None, {"python"}),
    ],
    ids=["valid", "invalid-key", "too-long", "no-tags", "case-insensitive"],
)
def test_tag_validation(
    labels: tuple[str, ...], expect_error: str | None, expected_tags: set[str]
) -> None:
    r = _compile([_snap(labels=labels)])
    if expect_error:
        assert expect_error in _err_codes(r)
    else:
        assert not r.has_errors
        assert {t.name for t in r.posts[0].tags} == expected_tags


# ---------------------------------------------------------------------------
# Error accumulation
# ---------------------------------------------------------------------------


def test_error_accumulation() -> None:
    # Multiple issues with errors
    r = _compile(
        [_snap(number=1, body="no front matter"), _snap(number=2, body="also none")]
    )
    assert r.has_errors and r.posts == ()
    assert {d.issue_number for d in r.diagnostics if d.severity == "error"} == {1, 2}
    # Any error prevents posts even if some are valid
    r2 = _compile([_snap(number=1), _snap(number=2, body="no front matter")])
    assert r2.has_errors and r2.posts == ()
    # No errors -> posts returned
    r3 = _compile(
        [
            _snap(number=1),
            _snap(
                number=2,
                body=(
                    '---\nslug: second\ndescription: d\ncreated_date: "2026-01-02"\n---\n\nBody two.'
                ),
            ),
        ]
    )
    assert not r3.has_errors and len(r3.posts) == 2
    # Empty title coexists with front-matter error
    r4 = _compile([_snap(title="", body="no front matter")])
    codes = _err_codes(r4)
    assert "TITLE_EMPTY" in codes and "FRONT_MATTER_MISSING" in codes


# ---------------------------------------------------------------------------
# Fullmatch kebab validation (trailing newline rejected)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body, labels, expect_code",
    [
        (
            '---\nslug: "my-post\\n"\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody',
            ("type:blog", "published"),
            "SLUG_INVALID",
        ),
        (_VALID_BODY, ("type:blog", "published", "tag:python\n"), "TAG_INVALID"),
    ],
    ids=["slug-trailing-newline", "tag-trailing-newline"],
)
def test_fullmatch_trailing_newline_rejected(
    body: str, labels: tuple[str, ...], expect_code: str
) -> None:
    r = _compile([_snap(body=body, labels=labels)])
    assert expect_code in _err_codes(r)


def test_fullmatch_valid_accepted() -> None:
    body = '---\nslug: my-post\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody'
    r = _compile(
        [
            _snap(
                body=body,
                labels=("type:blog", "published", "tag:python", "tag:web-dev"),
            )
        ]
    )
    assert not r.has_errors
    assert r.posts[0].slug == "my-post"
    assert {t.name for t in r.posts[0].tags} == {"python", "web-dev"}


# ---------------------------------------------------------------------------
# Unknown field / local error still participates in duplicate/reserved checks
# ---------------------------------------------------------------------------


def test_unknown_field_slug_participation() -> None:
    # Unknown field + duplicate slug
    body_unknown = (
        "---\nslug: dup\ndescription: A post.\n"
        'created_date: "2026-01-01"\nextra_field: value\n---\n\nBody one.'
    )
    body_valid = (
        "---\nslug: dup\ndescription: Another.\n"
        'created_date: "2026-01-02"\n---\n\nBody two.'
    )
    r = _compile([_snap(number=1, body=body_unknown), _snap(number=2, body=body_valid)])
    codes = _err_codes(r)
    assert "FRONT_MATTER_UNKNOWN_FIELD" in codes
    assert "SLUG_DUPLICATE" in codes
    # Unknown field + reserved slug
    body_reserved = (
        "---\nslug: page\ndescription: A post.\n"
        'created_date: "2026-01-01"\nextra_field: value\n---\n\nBody text.'
    )
    r2 = _compile([_snap(body=body_reserved)])
    codes2 = _err_codes(r2)
    assert "FRONT_MATTER_UNKNOWN_FIELD" in codes2
    assert "SLUG_RESERVED" in codes2
    # Unknown field not rendered into body
    from github_blog.utils.frontmatter import parse_front_matter

    parsed = parse_front_matter(
        "---\nslug: my-post\ndescription: A post.\n"
        'created_date: "2026-01-01"\nsecret_key: should_not_appear\n---\n\nVisible body.',
        collect_unknown_fields=True,
    )
    assert "should_not_appear" not in parsed.body
    assert parsed.body == "Visible body."


# ---------------------------------------------------------------------------
# Collaborator exception handling
# ---------------------------------------------------------------------------


def test_collaborator_exceptions_produce_diagnostics() -> None:
    def bad_md(_text: str) -> str:
        raise RuntimeError("md boom")

    def bad_san(_html: str) -> str:
        raise RuntimeError("san boom")

    # Markdown renderer exception
    r = BlogCompiler(_settings(), markdown_renderer=bad_md).compile([_snap(number=42)])
    assert r.has_errors and r.posts == ()
    d = next(d for d in r.diagnostics if d.code == "MARKDOWN_RENDER_FAILED")
    assert d.issue_number == 42 and d.field == "body"
    # Sanitizer exception
    r2 = BlogCompiler(_settings(), sanitizer=bad_san).compile([_snap(number=7)])
    assert "SANITIZER_FAILED" in _err_codes(r2, 7)
    # Multiple issues with collaborator errors accumulate
    r3 = BlogCompiler(_settings(), markdown_renderer=bad_md).compile(
        [
            _snap(number=1),
            _snap(
                number=2,
                body=(
                    '---\nslug: second\ndescription: d\ncreated_date: "2026-01-02"\n---\n\nBody two.'
                ),
            ),
        ]
    )
    md_errs = [d for d in r3.diagnostics if d.code == "MARKDOWN_RENDER_FAILED"]
    assert len(md_errs) == 2 and {d.issue_number for d in md_errs} == {1, 2}
    # Slug still participates in duplicate check
    r4 = BlogCompiler(_settings(), markdown_renderer=bad_md).compile(
        [_snap(number=1), _snap(number=2)]
    )
    assert "SLUG_DUPLICATE" in _err_codes(r4)


# ---------------------------------------------------------------------------
# Reserved slug
# ---------------------------------------------------------------------------


def test_reserved_slug() -> None:
    body = '---\nslug: page\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody'
    r = _compile([_snap(body=body)])
    assert "SLUG_RESERVED" in _err_codes(r)
    # With other errors
    body2 = '---\nslug: page\ndescription: d\ncreated_date: "2026-01-01"\n---\n\n'
    r2 = _compile([_snap(body=body2)])
    codes = _err_codes(r2)
    assert "SLUG_RESERVED" in codes and "BODY_EMPTY" in codes
    # Non-page slug not affected
    body3 = '---\nslug: my-post\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody'
    assert not _compile([_snap(body=body3)]).has_errors


# ---------------------------------------------------------------------------
# BlogPost fields, route, BlogTag
# ---------------------------------------------------------------------------


def test_blog_post_fields_and_route() -> None:
    r = _compile(
        [
            _snap(
                number=42,
                title="My Title",
                labels=("type:blog", "published", "tag:python"),
            )
        ]
    )
    assert not r.has_errors
    p = r.posts[0]
    assert p.issue_number == 42
    assert p.title == "My Title"
    assert p.slug == "my-first-post"
    assert p.description == "A test post about things."
    assert p.created_date == "2026-01-05"
    assert p.published_at == _DEFAULT_CREATED
    assert p.updated_at == _DEFAULT_UPDATED
    assert p.canonical_path == "/blog/my-first-post/"
    assert p.route.output_path == "blog/my-first-post/index.html"
    assert ".html" not in p.canonical_path
    # BlogTag
    tag = p.tags[0]
    assert isinstance(tag, BlogTag)
    assert tag.name == "python" and tag.path == "/tags/python/"
    # Route is fixed, not configurable
    from github_blog.config import PathsConfig

    s = _settings()
    s.paths = PathsConfig(blog="posts")
    r2 = BlogCompiler(s).compile([_snap()])
    assert r2.posts[0].canonical_path == "/blog/my-first-post/"


# ---------------------------------------------------------------------------
# Frozen model contract (immutable at runtime)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "obj, attr",
    [
        (
            IssueSnapshot(
                1, "t", "a", "b", (), _DEFAULT_CREATED, _DEFAULT_UPDATED, False
            ),
            "title",
        ),
        (BlogTag(name="x", path="/x/"), "name"),
        (_compile([_snap()]).posts[0], "slug"),
    ],
    ids=["issue_snapshot", "blog_tag", "blog_post"],
)
def test_frozen_content_models_reject_mutation(obj: object, attr: str) -> None:
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(obj, attr, "mutated")


# ---------------------------------------------------------------------------
# YAML scalar string type enforcement
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body, expect_code",
    [
        (
            '---\nslug: 123\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody',
            "SLUG_INVALID",
        ),
        (
            '---\nslug: x\ndescription: 123\ncreated_date: "2026-01-01"\n---\nbody',
            "DESCRIPTION_INVALID",
        ),
        (
            '---\nslug: [a, b]\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody',
            "SLUG_INVALID",
        ),
        (
            '---\nslug: x\ndescription: [a, b]\ncreated_date: "2026-01-01"\n---\nbody',
            "DESCRIPTION_INVALID",
        ),
    ],
    ids=["int-slug", "int-desc", "list-slug", "list-desc"],
)
def test_yaml_scalar_string_types(body: str, expect_code: str) -> None:
    assert expect_code in _err_codes(_compile([_snap(body=body)]))


def test_quoted_string_slug_accepted() -> None:
    body = '---\nslug: "my-post"\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody'
    r = _compile([_snap(body=body)])
    assert not r.has_errors and r.posts[0].slug == "my-post"


# ---------------------------------------------------------------------------
# Compiler -> two themes tracer
# ---------------------------------------------------------------------------


def _render_settings(theme: str) -> MagicMock:
    root = Path(__file__).parent.parent.absolute()
    s = MagicMock()
    s.paths.theme_path = root / "templates" / theme
    s.paths.seo_path = root / "templates" / "seo"
    s.paths.theme_url_path = f"/templates/{theme}"
    s.paths.rss = "atom.xml"
    s.paths.blog = "blog"
    s.site.title = "Tracer Blog"
    s.site.url = "https://example.com"
    s.site.author = "Author"
    s.site.description = "Desc"
    s.site.language = "en"
    s.github.username = "user"
    s.github.repo = "user/repo"
    s.seo.google_search_console = ""
    s.profile.avatar = ""
    s.profile.bio = "Bio"
    s.profile.links = []
    s.site.navigation.items = []
    s.branding.show_powered_by = True
    s.branding.powered_by_text = "Powered by"
    s.branding.powered_by_url = "https://github.com/geoqiao/github-blog"
    s.branding.show_intro = False
    s.branding.intro_text = ""
    s.branding.intro_text2 = ""
    s.branding.source_link_text = "View Source"
    s.branding.source_link_url = ""
    s.comments.provider = "utterances"
    s.comments.repo = ""
    s.comments.theme = "github-light"
    s.comments.theme_mode = "auto"
    return s


@pytest.mark.parametrize("theme", ["Escape1", "Escape2"])
def test_compiler_to_two_themes_tracer(tmp_path: Path, theme: str) -> None:
    from github_blog.services.render_service import RenderService

    renderer = RenderService(_render_settings(theme))
    snap = _snap(
        number=42,
        title="Tracer Post",
        body=(
            "---\nslug: tracer-post\ndescription: A tracer.\n"
            'created_date: "2026-01-05"\n---\n\nHello **world**.\n'
        ),
        labels=("type:blog", "published", "tag:python"),
    )
    result = _compile([snap])
    assert not result.has_errors
    post = result.posts[0]
    assert post.canonical_path == "/blog/tracer-post/"
    assert post.route.output_path == "blog/tracer-post/index.html"

    html = renderer.render_blog_detail(post)
    out = tmp_path / post.route.output_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    written = out.read_text(encoding="utf-8")
    assert "Tracer Post" in written
    assert "/blog/tracer-post/" in written
    assert "42" in written
    assert "<strong>world</strong>" in written
    assert "slug:" not in written
    assert "created_date" not in written
    assert "/tags/python/" in written
