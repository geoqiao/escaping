"""Tests for the Blog detail compiler (Ticket 04 primary seam).

The primary test seam: immutable ``IssueSnapshot`` values and content
policy go in; a ``BlogCompilationResult`` with compiled ``BlogPost``
values and accumulated diagnostics comes out.

These tests cover published Blog selection, complete front-matter envelope
and field validation, front-matter removal, GFM rendering + sanitization,
error accumulation, NFC/case-insensitive comparisons, and route output.
No GitHub, templates, or filesystem I/O are involved.
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
from github_blog.models.issue_snapshot import IssueSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_CREATED = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)
_DEFAULT_UPDATED = datetime(2026, 1, 11, 8, 30, tzinfo=timezone.utc)

_VALID_BODY = (
    "---\n"
    "slug: my-first-post\n"
    "description: A test post about things.\n"
    'created_date: "2026-01-05"\n'
    "---\n\n"
    "Hello **world**.\n"
)


def _make_snapshot(
    number: int = 1,
    *,
    title: str = "Test Post",
    body: str = _VALID_BODY,
    author: str = "alice",
    labels: tuple[str, ...] = ("type:blog", "published"),
    created_at: datetime = _DEFAULT_CREATED,
    updated_at: datetime = _DEFAULT_UPDATED,
    is_pull_request: bool = False,
) -> IssueSnapshot:
    return IssueSnapshot(
        number=number,
        title=title,
        author=author,
        body=body,
        labels=labels,
        created_at=created_at,
        updated_at=updated_at,
        is_pull_request=is_pull_request,
    )


def _make_settings(allowed_authors: list[str] | None = None) -> Settings:
    return Settings(
        github=GithubConfig(
            repo="user/repo",
            allowed_authors=allowed_authors or ["alice"],
        ),
        site=SiteConfig(
            title="Test Blog",
            url=HttpUrl("https://example.com/"),
            author="Test",
        ),
        about=AboutConfig(issue_number=1),
        security=SecurityConfig(token_env="G_T"),  # noqa: S106
    )


def _make_compiler(settings: Settings | None = None) -> BlogCompiler:
    return BlogCompiler(settings or _make_settings())


# ---------------------------------------------------------------------------
# Selection: PR exclusion
# ---------------------------------------------------------------------------


class TestPullRequestExclusion:
    def test_pr_excluded_no_error(self) -> None:
        snap = _make_snapshot(is_pull_request=True)
        result = _make_compiler().compile([snap])
        assert result.posts == ()
        assert not result.has_errors

    def test_pr_with_published_still_excluded(self) -> None:
        snap = _make_snapshot(
            is_pull_request=True,
            labels=("type:blog", "published"),
        )
        result = _make_compiler().compile([snap])
        assert result.posts == ()


# ---------------------------------------------------------------------------
# Selection: unauthorized author
# ---------------------------------------------------------------------------


class TestUnauthorizedAuthor:
    def test_unauthorized_warns_and_ignored(self) -> None:
        snap = _make_snapshot(author="bob")
        result = _make_compiler().compile([snap])
        assert result.posts == ()
        warnings = [d for d in result.diagnostics if d.severity == "warning"]
        assert len(warnings) == 1
        assert warnings[0].code == "UNAUTHORIZED_AUTHOR"
        assert warnings[0].issue_number == 1
        assert not result.has_errors

    def test_unauthorized_body_not_parsed(self) -> None:
        """Even a malformed body should not produce parsing diagnostics."""
        snap = _make_snapshot(
            author="bob",
            body="no front matter at all",
        )
        result = _make_compiler().compile([snap])
        # Only the warning, no parsing errors
        assert len(result.diagnostics) == 1
        assert result.diagnostics[0].severity == "warning"

    def test_author_case_insensitive(self) -> None:
        snap = _make_snapshot(author="Alice")
        result = _make_compiler().compile([snap])
        assert len(result.posts) == 1
        assert not result.has_errors


# ---------------------------------------------------------------------------
# Selection: unpublished
# ---------------------------------------------------------------------------


class TestUnpublishedIgnored:
    def test_unpublished_ignored_no_parsing(self) -> None:
        snap = _make_snapshot(
            labels=("type:blog",),
            body="totally invalid body with no front matter",
        )
        result = _make_compiler().compile([snap])
        assert result.posts == ()
        assert len(result.diagnostics) == 0

    def test_unpublished_malformed_body_no_diagnostics(self) -> None:
        snap = _make_snapshot(
            labels=("type:blog",),
            body="---\nslug: x\nslug: y\n---\nbody",
        )
        result = _make_compiler().compile([snap])
        assert len(result.diagnostics) == 0


# ---------------------------------------------------------------------------
# Selection: type label cardinality
# ---------------------------------------------------------------------------


class TestTypeLabelCardinality:
    def test_no_type_label_error(self) -> None:
        snap = _make_snapshot(labels=("published",))
        result = _make_compiler().compile([snap])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        assert any(d.code == "TYPE_LABEL_MISSING" for d in errors)

    def test_multiple_type_labels_error(self) -> None:
        snap = _make_snapshot(
            labels=("type:blog", "type:idea", "published"),
        )
        result = _make_compiler().compile([snap])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        assert any(d.code == "TYPE_LABEL_MULTIPLE" for d in errors)

    def test_unknown_type_label_error(self) -> None:
        snap = _make_snapshot(
            labels=("type:foo", "published"),
        )
        result = _make_compiler().compile([snap])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        assert any(d.code == "TYPE_LABEL_UNKNOWN" for d in errors)

    def test_type_idea_skipped_not_blog(self) -> None:
        snap = _make_snapshot(labels=("type:idea", "published"))
        result = _make_compiler().compile([snap])
        assert result.posts == ()
        assert not result.has_errors

    def test_type_about_skipped_not_blog(self) -> None:
        snap = _make_snapshot(labels=("type:about", "published"))
        result = _make_compiler().compile([snap])
        assert result.posts == ()
        assert not result.has_errors

    def test_type_label_case_insensitive(self) -> None:
        snap = _make_snapshot(labels=("Type:Blog", "Published"))
        result = _make_compiler().compile([snap])
        assert len(result.posts) == 1


# ---------------------------------------------------------------------------
# Front-matter validation
# ---------------------------------------------------------------------------


class TestFrontMatterValidation:
    def test_missing_front_matter_error(self) -> None:
        snap = _make_snapshot(body="No front matter here.")
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "FRONT_MATTER_MISSING" and d.issue_number == 1
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_unclosed_front_matter_error(self) -> None:
        snap = _make_snapshot(body="---\nslug: x\nbody without close")
        result = _make_compiler().compile([snap])
        assert result.has_errors

    def test_front_matter_not_mapping_error(self) -> None:
        snap = _make_snapshot(body="---\n- item1\n- item2\n---\nbody")
        result = _make_compiler().compile([snap])
        assert result.has_errors

    def test_duplicate_keys_error(self) -> None:
        snap = _make_snapshot(body="---\nslug: a\nslug: b\n---\nbody")
        result = _make_compiler().compile([snap])
        assert result.has_errors

    def test_unknown_field_error(self) -> None:
        snap = _make_snapshot(
            body='---\nslug: x\ndescription: d\ncreated_date: "2026-01-01"\nfoo: bar\n---\nbody'
        )
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "FRONT_MATTER_UNKNOWN_FIELD"
            for d in result.diagnostics
            if d.severity == "error"
        )


# ---------------------------------------------------------------------------
# Field validation: slug
# ---------------------------------------------------------------------------


class TestSlugValidation:
    def test_missing_slug_error(self) -> None:
        body = '---\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody'
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "SLUG_MISSING"
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_invalid_slug_format_error(self) -> None:
        body = '---\nslug: Invalid Slug!\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody'
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "SLUG_INVALID"
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_slug_too_long_error(self) -> None:
        slug = "a" * 81
        body = (
            f'---\nslug: {slug}\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody'
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "SLUG_INVALID"
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_valid_slug_accepted(self) -> None:
        body = '---\nslug: my-post-123\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody'
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        assert result.posts[0].slug == "my-post-123"

    def test_duplicate_slug_error(self) -> None:
        body = '---\nslug: dup\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody'
        snap1 = _make_snapshot(number=1, body=body)
        snap2 = _make_snapshot(number=2, body=body)
        result = _make_compiler().compile([snap1, snap2])
        assert result.has_errors
        assert any(
            d.code == "SLUG_DUPLICATE"
            for d in result.diagnostics
            if d.severity == "error"
        )


# ---------------------------------------------------------------------------
# Field validation: description
# ---------------------------------------------------------------------------


class TestDescriptionValidation:
    def test_missing_description_error(self) -> None:
        body = '---\nslug: x\ncreated_date: "2026-01-01"\n---\nbody'
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "DESCRIPTION_MISSING"
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_empty_description_error(self) -> None:
        body = '---\nslug: x\ndescription: ""\ncreated_date: "2026-01-01"\n---\nbody'
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors

    def test_description_with_control_char_error(self) -> None:
        # Use a literal tab character (control char)
        body = '---\nslug: x\ndescription: "has\\ttab"\ncreated_date: "2026-01-01"\n---\nbody'
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "DESCRIPTION_INVALID"
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_description_with_newline_error(self) -> None:
        body = (
            "---\nslug: x\ndescription: |\n  line1\n  line2\n"
            'created_date: "2026-01-01"\n---\nbody'
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors

    def test_description_with_angle_brackets_error(self) -> None:
        body = '---\nslug: x\ndescription: "has <tag>"\ncreated_date: "2026-01-01"\n---\nbody'
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "DESCRIPTION_INVALID"
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_description_too_long_error(self) -> None:
        desc = "x" * 301
        body = (
            f'---\nslug: x\ndescription: {desc}\ncreated_date: "2026-01-01"\n---\nbody'
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "DESCRIPTION_TOO_LONG"
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_description_300_chars_accepted(self) -> None:
        desc = "x" * 300
        body = (
            f'---\nslug: x\ndescription: {desc}\ncreated_date: "2026-01-01"\n---\nbody'
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert not result.has_errors


# ---------------------------------------------------------------------------
# Field validation: created_date
# ---------------------------------------------------------------------------


class TestCreatedDateValidation:
    def test_missing_created_date_error(self) -> None:
        body = "---\nslug: x\ndescription: d\n---\nbody"
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "CREATED_DATE_MISSING"
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_invalid_date_format_error(self) -> None:
        body = '---\nslug: x\ndescription: d\ncreated_date: "2026/01/01"\n---\nbody'
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "CREATED_DATE_INVALID"
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_invalid_date_value_error(self) -> None:
        # Passes regex but is not a real date (Feb 30)
        body = '---\nslug: x\ndescription: d\ncreated_date: "2026-02-30"\n---\nbody'
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "CREATED_DATE_INVALID"
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_valid_date_accepted(self) -> None:
        body = '---\nslug: x\ndescription: d\ncreated_date: "2026-03-15"\n---\nbody'
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        assert result.posts[0].created_date == "2026-03-15"


class TestCreatedDateStyleValidation:
    """created_date must be a YAML quoted scalar (single or double quote).

    The parser captures node-level YAML style metadata so the compiler can
    distinguish quoted scalars from plain, literal-block, and folded-block
    scalars -- all of which construct to the same Python ``str`` value.
    """

    def test_single_quoted_created_date_accepted(self) -> None:
        body = "---\nslug: x\ndescription: d\ncreated_date: '2026-01-01'\n---\nbody"
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        assert result.posts[0].created_date == "2026-01-01"

    def test_double_quoted_created_date_accepted(self) -> None:
        body = '---\nslug: x\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody'
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        assert result.posts[0].created_date == "2026-01-01"

    def test_plain_created_date_rejected(self) -> None:
        body = "---\nslug: x\ndescription: d\ncreated_date: 2026-01-01\n---\nbody"
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "CREATED_DATE_INVALID"
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_explicit_str_tag_created_date_rejected(self) -> None:
        """``!!str 2026-01-01`` constructs to a Python ``str`` but is plain
        style -- must be rejected."""
        body = "---\nslug: x\ndescription: d\ncreated_date: !!str 2026-01-01\n---\nbody"
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "CREATED_DATE_INVALID"
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_literal_block_created_date_rejected(self) -> None:
        body = "---\nslug: x\ndescription: d\ncreated_date: |-\n  2026-01-01\n---\nbody"
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "CREATED_DATE_INVALID"
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_folded_block_created_date_rejected(self) -> None:
        body = "---\nslug: x\ndescription: d\ncreated_date: >-\n  2026-01-01\n---\nbody"
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "CREATED_DATE_INVALID"
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_rejection_returns_no_exception(self) -> None:
        """Style rejection must produce a diagnostic, not raise."""
        body = "---\nslug: x\ndescription: d\ncreated_date: !!str 2026-01-01\n---\nbody"
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        diag = next(d for d in result.diagnostics if d.code == "CREATED_DATE_INVALID")
        assert diag.issue_number == snap.number
        assert diag.field == "created_date"


# ---------------------------------------------------------------------------
# Field validation: title and body
# ---------------------------------------------------------------------------


class TestTitleAndBodyValidation:
    def test_empty_title_error(self) -> None:
        snap = _make_snapshot(title="")
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "TITLE_EMPTY" for d in result.diagnostics if d.severity == "error"
        )

    def test_empty_body_error(self) -> None:
        body = '---\nslug: x\ndescription: d\ncreated_date: "2026-01-01"\n---\n\n'
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "BODY_EMPTY" for d in result.diagnostics if d.severity == "error"
        )

    def test_whitespace_only_body_error(self) -> None:
        body = (
            '---\nslug: x\ndescription: d\ncreated_date: "2026-01-01"\n---\n   \n  \n'
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors


# ---------------------------------------------------------------------------
# Front-matter removal
# ---------------------------------------------------------------------------


class TestFrontMatterRemoval:
    def test_front_matter_not_in_body_html(self) -> None:
        body = (
            "---\n"
            "slug: secret-slug-value\n"
            "description: A post.\n"
            'created_date: "2026-01-01"\n'
            "---\n\n"
            "Visible content."
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        html = result.posts[0].body_html
        assert "secret-slug-value" not in html
        assert "created_date" not in html
        assert "Visible content." in html

    def test_body_html_is_sanitized(self) -> None:
        """Dangerous HTML in the markdown body is removed."""
        body = (
            "---\n"
            "slug: x\n"
            "description: d\n"
            'created_date: "2026-01-01"\n'
            "---\n\n"
            "<script>alert(1)</script>\n\nNormal text."
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        html = result.posts[0].body_html
        assert "<script" not in html.lower()
        assert "alert" not in html
        assert "Normal text." in html


# ---------------------------------------------------------------------------
# Tag validation
# ---------------------------------------------------------------------------


class TestTagValidation:
    def test_valid_tags_extracted(self) -> None:
        snap = _make_snapshot(
            labels=("type:blog", "published", "tag:python", "tag:rust"),
        )
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        assert {t.name for t in result.posts[0].tags} == {"python", "rust"}

    def test_invalid_tag_key_error(self) -> None:
        snap = _make_snapshot(
            labels=("type:blog", "published", "tag:Python_Web"),
        )
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "TAG_INVALID" for d in result.diagnostics if d.severity == "error"
        )

    def test_tag_too_long_error(self) -> None:
        tag_key = "a" * 51
        snap = _make_snapshot(
            labels=("type:blog", "published", f"tag:{tag_key}"),
        )
        result = _make_compiler().compile([snap])
        assert result.has_errors

    def test_no_tags_accepted(self) -> None:
        snap = _make_snapshot(labels=("type:blog", "published"))
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        assert result.posts[0].tags == ()

    def test_tag_label_case_insensitive(self) -> None:
        snap = _make_snapshot(
            labels=("type:blog", "published", "Tag:Python"),
        )
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        assert "python" in {t.name for t in result.posts[0].tags}


# ---------------------------------------------------------------------------
# Error accumulation
# ---------------------------------------------------------------------------


class TestErrorAccumulation:
    def test_multiple_errors_returned_together(self) -> None:
        snap1 = _make_snapshot(number=1, body="no front matter")
        snap2 = _make_snapshot(number=2, body="also no front matter")
        result = _make_compiler().compile([snap1, snap2])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        assert len(errors) == 2
        issue_numbers = {d.issue_number for d in errors}
        assert issue_numbers == {1, 2}

    def test_any_error_prevents_posts(self) -> None:
        snap1 = _make_snapshot(number=1)  # valid
        snap2 = _make_snapshot(number=2, body="no front matter")  # invalid
        result = _make_compiler().compile([snap1, snap2])
        assert result.has_errors
        # No posts when any error exists
        assert result.posts == ()

    def test_valid_posts_returned_when_no_errors(self) -> None:
        snap1 = _make_snapshot(number=1, body=_VALID_BODY)
        snap2 = _make_snapshot(
            number=2,
            body=(
                "---\nslug: second-post\ndescription: d\n"
                'created_date: "2026-01-02"\n---\n\nBody two.'
            ),
        )
        result = _make_compiler().compile([snap1, snap2])
        assert not result.has_errors
        assert len(result.posts) == 2


# ---------------------------------------------------------------------------
# BlogPost model fields
# ---------------------------------------------------------------------------


class TestBlogPostFields:
    def test_post_contains_all_required_fields(self) -> None:
        snap = _make_snapshot(
            number=42,
            title="My Title",
            labels=("type:blog", "published", "tag:python"),
        )
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        post = result.posts[0]
        assert post.issue_number == 42
        assert post.title == "My Title"
        assert post.slug == "my-first-post"
        assert post.description == "A test post about things."
        assert post.created_date == "2026-01-05"
        assert post.published_at == _DEFAULT_CREATED
        assert post.updated_at == _DEFAULT_UPDATED
        assert post.tags[0].name == "python"
        assert "Hello" in post.body_html
        assert "<strong>world</strong>" in post.body_html
        assert post.canonical_path == "/blog/my-first-post/"

    def test_post_is_immutable(self) -> None:
        snap = _make_snapshot()
        result = _make_compiler().compile([snap])
        post = result.posts[0]
        import dataclasses

        with pytest.raises(dataclasses.FrozenInstanceError):
            post.title = "changed"  # type: ignore


# ---------------------------------------------------------------------------
# Route: canonical path and output
# ---------------------------------------------------------------------------


class TestRouteMapping:
    def test_canonical_path_uses_trailing_slash(self) -> None:
        snap = _make_snapshot()
        result = _make_compiler().compile([snap])
        assert result.posts[0].canonical_path == "/blog/my-first-post/"

    def test_canonical_path_no_html_extension(self) -> None:
        snap = _make_snapshot()
        result = _make_compiler().compile([snap])
        assert ".html" not in result.posts[0].canonical_path

    def test_canonical_path_is_fixed_not_configurable(self) -> None:
        """Blog routes are fixed at /blog/{slug}/ regardless of paths.blog config."""
        from github_blog.config import PathsConfig

        settings = _make_settings()
        settings.paths = PathsConfig(blog="posts")
        snap = _make_snapshot()
        result = BlogCompiler(settings).compile([snap])
        assert result.posts[0].canonical_path == "/blog/my-first-post/"

    def test_blog_route_output_path(self) -> None:
        """BlogPost.route returns a BlogRoute with fixed output_path."""
        snap = _make_snapshot()
        result = _make_compiler().compile([snap])
        route = result.posts[0].route
        assert route.canonical_path == "/blog/my-first-post/"
        assert route.output_path == "blog/my-first-post/index.html"


# ---------------------------------------------------------------------------
# NFC normalization
# ---------------------------------------------------------------------------


class TestNFCNormalization:
    def test_nfc_author_matching(self) -> None:
        # "alice" with combining characters -> NFC normalized
        snap = _make_snapshot(author="alice")
        result = _make_compiler(_make_settings(allowed_authors=["alice"])).compile(
            [snap]
        )
        assert len(result.posts) == 1


# ---------------------------------------------------------------------------
# Integration: compiler -> renderer (secondary seam)
# ---------------------------------------------------------------------------


class TestCompilerToRendererIntegration:
    """Verify the secondary seam: BlogPost -> canonical rendered page."""

    def test_compiled_post_renders_through_render_service(self) -> None:
        from pathlib import Path

        from github_blog.services.render_service import RenderService

        project_root = Path(__file__).parent.parent.absolute()
        settings = MagicMock()
        settings.paths.theme_path = project_root / "templates" / "Escape1"
        settings.paths.seo_path = project_root / "templates" / "seo"
        settings.paths.theme_url_path = "/templates/Escape1"
        settings.paths.rss = "atom.xml"
        settings.paths.blog = "blog"
        settings.site.title = "Test Blog"
        settings.site.url = "https://example.com"
        settings.site.author = "Author"
        settings.site.description = "Test Description"
        settings.site.language = "en"
        settings.github.username = "user"
        settings.github.repo = "user/repo"
        settings.seo.google_search_console = ""
        settings.profile.avatar = ""
        settings.profile.bio = "Test bio"
        settings.profile.links = []
        settings.site.navigation.items = []
        settings.branding.show_powered_by = True
        settings.branding.powered_by_text = "Powered by"
        settings.branding.powered_by_url = "https://github.com/geoqiao/github-blog"
        settings.branding.show_intro = False
        settings.branding.intro_text = ""
        settings.branding.intro_text2 = ""
        settings.branding.source_link_text = "View Source"
        settings.branding.source_link_url = ""
        settings.comments.provider = "utterances"
        settings.comments.repo = ""
        settings.comments.theme = "github-light"
        settings.comments.theme_mode = "auto"

        renderer = RenderService(settings)
        snap = _make_snapshot(number=42, title="Compiled Post")
        result = _make_compiler().compile([snap])
        assert not result.has_errors

        html = renderer.render_blog_detail(result.posts[0])
        assert "Compiled Post" in html
        assert "/blog/my-first-post/" in html
        assert "42" in html

    def test_compiled_post_renders_escape2(self) -> None:
        from pathlib import Path

        from github_blog.services.render_service import RenderService

        project_root = Path(__file__).parent.parent.absolute()
        settings = MagicMock()
        settings.paths.theme_path = project_root / "templates" / "Escape2"
        settings.paths.seo_path = project_root / "templates" / "seo"
        settings.paths.theme_url_path = "/templates/Escape2"
        settings.paths.rss = "atom.xml"
        settings.paths.blog = "blog"
        settings.site.title = "Test Blog"
        settings.site.url = "https://example.com"
        settings.site.author = "Author"
        settings.site.description = "Test Description"
        settings.site.language = "en"
        settings.github.username = "user"
        settings.github.repo = "user/repo"
        settings.seo.google_search_console = ""
        settings.profile.avatar = ""
        settings.profile.bio = "Test bio"
        settings.profile.links = []
        settings.site.navigation.items = []
        settings.branding.show_powered_by = True
        settings.branding.powered_by_text = "Powered by"
        settings.branding.powered_by_url = "https://github.com/geoqiao/github-blog"
        settings.branding.show_intro = False
        settings.branding.intro_text = ""
        settings.branding.intro_text2 = ""
        settings.branding.source_link_text = "View Source"
        settings.branding.source_link_url = ""
        settings.comments.provider = "utterances"
        settings.comments.repo = ""
        settings.comments.theme = "github-light"
        settings.comments.theme_mode = "auto"

        renderer = RenderService(settings)
        snap = _make_snapshot(number=7, title="Escape2 Post")
        result = _make_compiler().compile([snap])
        assert not result.has_errors

        html = renderer.render_blog_detail(result.posts[0])
        assert "Escape2 Post" in html
        assert "/blog/my-first-post/" in html
        assert "7" in html

    def test_errors_prevent_rendering(self) -> None:
        """When compilation has errors, no posts are available to render."""
        snap = _make_snapshot(body="no front matter")
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert result.posts == ()
        # Caller must not attempt to render when has_errors is True


# ---------------------------------------------------------------------------
# YAML scalar string type enforcement (Requirement 4)
# ---------------------------------------------------------------------------


class TestYamlScalarStringTypes:
    """slug and description must be exact YAML string scalars."""

    def test_integer_slug_rejected(self) -> None:
        body = '---\nslug: 123\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody'
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "SLUG_INVALID"
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_integer_description_rejected(self) -> None:
        body = '---\nslug: x\ndescription: 123\ncreated_date: "2026-01-01"\n---\nbody'
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "DESCRIPTION_INVALID"
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_list_slug_rejected(self) -> None:
        body = (
            '---\nslug: [a, b]\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody'
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors

    def test_list_description_rejected(self) -> None:
        body = (
            '---\nslug: x\ndescription: [a, b]\ncreated_date: "2026-01-01"\n---\nbody'
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors

    def test_quoted_string_slug_accepted(self) -> None:
        body = '---\nslug: "my-post"\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody'
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        assert result.posts[0].slug == "my-post"


class TestDescriptionLineSeparators:
    """Reject U+2028/U+2029 and Unicode control characters in description."""

    def test_line_separator_in_description_rejected(self) -> None:
        body = (
            '---\nslug: x\ndescription: "line1\u2028line2"\n'
            'created_date: "2026-01-01"\n---\nbody'
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "DESCRIPTION_INVALID"
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_paragraph_separator_in_description_rejected(self) -> None:
        body = (
            '---\nslug: x\ndescription: "line1\u2029line2"\n'
            'created_date: "2026-01-01"\n---\nbody'
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors

    def test_c1_control_char_in_description_rejected(self) -> None:
        # U+0081 is a C1 control character that YAML does not fold.
        body = (
            '---\nslug: x\ndescription: "has\u0081char"\n'
            'created_date: "2026-01-01"\n---\nbody'
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors

    def test_description_300_codepoints_still_accepted(self) -> None:
        """Preserve the 300-codepoint bound."""
        desc = "x" * 300
        body = (
            f'---\nslug: x\ndescription: {desc}\ncreated_date: "2026-01-01"\n---\nbody'
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert not result.has_errors


# ---------------------------------------------------------------------------
# Error accumulation (Requirement 5)
# ---------------------------------------------------------------------------


class TestMultiErrorAccumulation:
    """All detectable errors must coexist, not short-circuit."""

    def test_empty_title_coexists_with_frontmatter_error(self) -> None:
        """Empty title and missing front matter should both be reported."""
        snap = _make_snapshot(title="", body="no front matter")
        result = _make_compiler().compile([snap])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        assert any(d.code == "TITLE_EMPTY" for d in errors)
        assert any(d.code == "FRONT_MATTER_MISSING" for d in errors)

    def test_empty_title_coexists_with_field_errors(self) -> None:
        """Empty title and field errors should both be reported."""
        body = "---\ndescription: d\n---\nbody"
        snap = _make_snapshot(title="", body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        assert any(d.code == "TITLE_EMPTY" for d in errors)
        assert any(d.code == "SLUG_MISSING" for d in errors)
        assert any(d.code == "CREATED_DATE_MISSING" for d in errors)

    def test_empty_title_coexists_with_body_error(self) -> None:
        """Empty title and empty body should both be reported."""
        body = '---\nslug: x\ndescription: d\ncreated_date: "2026-01-01"\n---\n\n'
        snap = _make_snapshot(title="", body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        assert any(d.code == "TITLE_EMPTY" for d in errors)
        assert any(d.code == "BODY_EMPTY" for d in errors)

    def test_valid_slug_participates_in_duplicate_check_with_other_errors(self) -> None:
        """A valid slug with other local errors must still be checked for duplicates."""
        # Issue 1: valid slug "dup" but empty body.
        body1 = '---\nslug: dup\ndescription: d\ncreated_date: "2026-01-01"\n---\n\n'
        snap1 = _make_snapshot(number=1, body=body1)
        # Issue 2: valid slug "dup" and valid body.
        body2 = (
            '---\nslug: dup\ndescription: d\ncreated_date: "2026-01-01"\n---\n\nbody'
        )
        snap2 = _make_snapshot(number=2, body=body2)
        result = _make_compiler().compile([snap1, snap2])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        # Issue 1 should have BODY_EMPTY.
        assert any(d.code == "BODY_EMPTY" and d.issue_number == 1 for d in errors)
        # And SLUG_DUPLICATE should be reported for the collision.
        assert any(d.code == "SLUG_DUPLICATE" for d in errors)

    def test_multiple_type_label_diagnostics_aggregated(self) -> None:
        """Multiple type-label errors (MULTIPLE + UNKNOWN) are both reported."""
        snap = _make_snapshot(
            labels=("type:blog", "type:idea", "type:foo", "published"),
        )
        result = _make_compiler().compile([snap])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        assert any(d.code == "TYPE_LABEL_MULTIPLE" for d in errors)
        assert any(d.code == "TYPE_LABEL_UNKNOWN" for d in errors)

    def test_supported_plus_unknown_type_multiple_and_unknown(self) -> None:
        """type:blog + type:foo must report BOTH MULTIPLE and UNKNOWN."""
        snap = _make_snapshot(
            labels=("type:blog", "type:foo", "published"),
        )
        result = _make_compiler().compile([snap])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        assert any(d.code == "TYPE_LABEL_MULTIPLE" for d in errors)
        assert any(d.code == "TYPE_LABEL_UNKNOWN" for d in errors)

    def test_two_unknown_types_multiple_and_unknown(self) -> None:
        """Two distinct unknown types must report BOTH MULTIPLE and UNKNOWN."""
        snap = _make_snapshot(
            labels=("type:foo", "type:bar", "published"),
        )
        result = _make_compiler().compile([snap])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        assert any(d.code == "TYPE_LABEL_MULTIPLE" for d in errors)
        assert any(d.code == "TYPE_LABEL_UNKNOWN" for d in errors)

    def test_duplicate_unknown_type_multiple_and_unknown(self) -> None:
        """Duplicate unknown type:foo + type:foo must report BOTH MULTIPLE and UNKNOWN."""
        snap = _make_snapshot(
            labels=("type:foo", "type:foo", "published"),
        )
        result = _make_compiler().compile([snap])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        assert any(d.code == "TYPE_LABEL_MULTIPLE" for d in errors)
        assert any(d.code == "TYPE_LABEL_UNKNOWN" for d in errors)

    def test_single_unknown_type_only_unknown_not_multiple(self) -> None:
        """A single unknown type must report UNKNOWN but NOT MULTIPLE."""
        snap = _make_snapshot(
            labels=("type:foo", "published"),
        )
        result = _make_compiler().compile([snap])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        assert any(d.code == "TYPE_LABEL_UNKNOWN" for d in errors)
        assert not any(d.code == "TYPE_LABEL_MULTIPLE" for d in errors)


# ---------------------------------------------------------------------------
# Reserved slug collision (Requirement 9)
# ---------------------------------------------------------------------------


class TestReservedSlug:
    """Reserved Blog-detail slug 'page' must be rejected for pagination collision."""

    def test_reserved_slug_page_rejected(self) -> None:
        body = '---\nslug: page\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody'
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "SLUG_RESERVED"
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_reserved_slug_page_with_other_errors(self) -> None:
        """Reserved slug is detected even when other local errors exist."""
        body = '---\nslug: page\ndescription: d\ncreated_date: "2026-01-01"\n---\n\n'
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        assert any(d.code == "SLUG_RESERVED" for d in errors)
        assert any(d.code == "BODY_EMPTY" for d in errors)


# ---------------------------------------------------------------------------
# Sanitizer regression tests through full BlogCompiler path (Requirement 3)
# ---------------------------------------------------------------------------


class TestSanitizerRegressionThroughCompiler:
    """Security regression tests through the full BlogCompiler path."""

    def test_entity_decoded_tag_injection_through_compiler(self) -> None:
        body = (
            '---\nslug: x\ndescription: d\ncreated_date: "2026-01-01"\n---\n\n'
            "&lt;script&gt;alert(1)&lt;/script&gt;\n\nNormal text."
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        html = result.posts[0].body_html
        assert "<script" not in html.lower()
        assert "Normal text." in html

    def test_attribute_breakout_through_compiler(self) -> None:
        body = (
            '---\nslug: x\ndescription: d\ncreated_date: "2026-01-01"\n---\n\n'
            '<img src="https://example.com/img.png" alt="a&quot; onmouseover=&quot;alert(1)" />\n\nText.'
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        html = result.posts[0].body_html
        assert 'onmouseover="' not in html.lower()
        assert "onmouseover='" not in html.lower()

    def test_obfuscated_scheme_through_compiler(self) -> None:
        body = (
            '---\nslug: x\ndescription: d\ncreated_date: "2026-01-01"\n---\n\n'
            '<a href="java\tscript:alert(1)">click</a>\n\nText.'
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        html = result.posts[0].body_html
        assert "javascript:" not in html.lower()

    def test_normal_markdown_images_preserved_through_compiler(self) -> None:
        body = (
            '---\nslug: x\ndescription: d\ncreated_date: "2026-01-01"\n---\n\n'
            "![alt](https://github.com/user-attachments/assets/abc.png)\n\nText."
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        html = result.posts[0].body_html
        assert "github.com/user-attachments/assets/abc.png" in html
        assert "<img" in html


# ---------------------------------------------------------------------------
# Unknown front-matter field does not block global slug diagnostics (Finding 3)
# ---------------------------------------------------------------------------


class TestUnknownFieldDoesNotBlockSlugDiagnostics:
    """An Issue with a valid slug + unknown field must still participate in
    SLUG_DUPLICATE / SLUG_RESERVED global checks while reporting
    FRONT_MATTER_UNKNOWN_FIELD.  Unknown metadata must not be rendered into
    the body.
    """

    def test_unknown_field_reports_error(self) -> None:
        body = (
            "---\n"
            "slug: my-post\n"
            "description: A post.\n"
            'created_date: "2026-01-01"\n'
            "foo: bar\n"
            "---\n\n"
            "Body text."
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "FRONT_MATTER_UNKNOWN_FIELD"
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_unknown_field_with_duplicate_slug(self) -> None:
        """Valid slug + unknown field must still trigger SLUG_DUPLICATE."""
        body_with_unknown = (
            "---\n"
            "slug: dup\n"
            "description: A post.\n"
            'created_date: "2026-01-01"\n'
            "extra_field: value\n"
            "---\n\n"
            "Body one."
        )
        body_valid = (
            "---\n"
            "slug: dup\n"
            "description: Another post.\n"
            'created_date: "2026-01-02"\n'
            "---\n\n"
            "Body two."
        )
        snap1 = _make_snapshot(number=1, body=body_with_unknown)
        snap2 = _make_snapshot(number=2, body=body_valid)
        result = _make_compiler().compile([snap1, snap2])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        # Issue 1 reports FRONT_MATTER_UNKNOWN_FIELD.
        assert any(
            d.code == "FRONT_MATTER_UNKNOWN_FIELD" and d.issue_number == 1
            for d in errors
        )
        # And SLUG_DUPLICATE is reported for the collision.
        assert any(d.code == "SLUG_DUPLICATE" for d in errors)

    def test_unknown_field_with_reserved_slug(self) -> None:
        """Valid reserved slug + unknown field must trigger SLUG_RESERVED."""
        body = (
            "---\n"
            "slug: page\n"
            "description: A post.\n"
            'created_date: "2026-01-01"\n'
            "extra_field: value\n"
            "---\n\n"
            "Body text."
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        assert any(d.code == "FRONT_MATTER_UNKNOWN_FIELD" for d in errors)
        assert any(d.code == "SLUG_RESERVED" for d in errors)

    def test_unknown_field_not_rendered_into_body(self) -> None:
        """Unknown field metadata must not appear in rendered body HTML.

        Since compilation fails, no post is produced.  We verify that the
        parsed body (returned by the lenient parse) does not contain the
        unknown field value.
        """
        from github_blog.utils.frontmatter import parse_front_matter

        body = (
            "---\n"
            "slug: my-post\n"
            "description: A post.\n"
            'created_date: "2026-01-01"\n'
            "secret_key: should_not_appear\n"
            "---\n\n"
            "Visible body."
        )
        result = parse_front_matter(body, collect_unknown_fields=True)
        assert "should_not_appear" not in result.body
        assert "secret_key" not in result.body
        assert result.body == "Visible body."
        assert "secret_key" in result.unknown_fields
        assert "slug" in result.fields
        assert "secret_key" not in result.fields


# ---------------------------------------------------------------------------
# Full-string kebab validation (Correctness #4)
# ---------------------------------------------------------------------------


class TestFullStringKebabValidation:
    """Slug and tag kebab validation must use full-string semantics.

    ``re.match`` with ``$`` allows a trailing newline because ``$`` matches
    before a trailing ``\n``.  ``fullmatch`` requires the entire string to
    match, correctly rejecting values with trailing newlines or other
    extra characters.
    """

    def test_slug_with_trailing_newline_rejected(self) -> None:
        # Use YAML escape \n to embed a literal newline in the slug value.
        # ``re.match`` with ``$`` would accept this because ``$`` matches
        # before a trailing newline; ``fullmatch`` correctly rejects it.
        body = (
            '---\nslug: "my-post\\n"\ndescription: d\n'
            'created_date: "2026-01-01"\n---\nbody'
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "SLUG_INVALID"
            for d in result.diagnostics
            if d.severity == "error"
        )

    def test_tag_with_trailing_newline_rejected(self) -> None:
        # A label whose value after "tag:" has a trailing newline must be
        # rejected, not silently accepted as a valid tag key.
        snap = _make_snapshot(
            labels=("type:blog", "published", "tag:python\n"),
        )
        result = _make_compiler().compile([snap])
        assert result.has_errors
        assert any(
            d.code == "TAG_INVALID" for d in result.diagnostics if d.severity == "error"
        )

    def test_valid_slug_without_trailing_chars_accepted(self) -> None:
        """Regression: normal valid slugs still pass with fullmatch."""
        body = (
            '---\nslug: my-post\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody'
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        assert result.posts[0].slug == "my-post"

    def test_valid_tag_without_trailing_chars_accepted(self) -> None:
        """Regression: normal valid tags still pass with fullmatch."""
        snap = _make_snapshot(
            labels=("type:blog", "published", "tag:python", "tag:web-dev"),
        )
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        assert {t.name for t in result.posts[0].tags} == {"python", "web-dev"}


# ---------------------------------------------------------------------------
# Collaborator exception handling (Correctness #5)
# ---------------------------------------------------------------------------


class TestCollaboratorExceptionHandling:
    """BlogCompiler must catch markdown renderer and sanitizer exceptions,
    convert them to per-Issue structured Diagnostics with ``field='body'``,
    and continue processing remaining Issues.  Any error makes posts empty.
    """

    def test_markdown_renderer_exception_produces_diagnostic(self) -> None:
        def bad_renderer(_text: str) -> str:
            raise RuntimeError("markdown boom")

        compiler = BlogCompiler(_make_settings(), markdown_renderer=bad_renderer)
        snap = _make_snapshot(number=42)
        result = compiler.compile([snap])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        assert any(d.code == "MARKDOWN_RENDER_FAILED" for d in errors)
        diag = next(d for d in errors if d.code == "MARKDOWN_RENDER_FAILED")
        assert diag.issue_number == 42
        assert diag.field == "body"
        assert result.posts == ()

    def test_sanitizer_exception_produces_diagnostic(self) -> None:
        def bad_sanitizer(_html: str) -> str:
            raise RuntimeError("sanitizer boom")

        compiler = BlogCompiler(_make_settings(), sanitizer=bad_sanitizer)
        snap = _make_snapshot(number=7)
        result = compiler.compile([snap])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        assert any(d.code == "SANITIZER_FAILED" for d in errors)
        diag = next(d for d in errors if d.code == "SANITIZER_FAILED")
        assert diag.issue_number == 7
        assert diag.field == "body"
        assert result.posts == ()

    def test_markdown_error_does_not_escape_compile(self) -> None:
        """No exception should escape the compile() call."""

        def bad_renderer(_text: str) -> str:
            raise RuntimeError("escape test")

        compiler = BlogCompiler(_make_settings(), markdown_renderer=bad_renderer)
        # Must not raise.
        result = compiler.compile([_make_snapshot()])
        assert result.has_errors

    def test_multiple_issues_with_collaborator_errors_accumulate(self) -> None:
        """When two Issues both have markdown renderer failures, both errors
        are reported and posts is empty."""
        call_count = 0

        def bad_renderer(_text: str) -> str:
            nonlocal call_count
            call_count += 1
            raise RuntimeError(f"boom #{call_count}")

        compiler = BlogCompiler(_make_settings(), markdown_renderer=bad_renderer)
        snap1 = _make_snapshot(number=1, body=_VALID_BODY)
        snap2 = _make_snapshot(
            number=2,
            body=(
                "---\nslug: second\ndescription: d\n"
                'created_date: "2026-01-02"\n---\n\nBody two.'
            ),
        )
        result = compiler.compile([snap1, snap2])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        markdown_errors = [d for d in errors if d.code == "MARKDOWN_RENDER_FAILED"]
        assert len(markdown_errors) == 2
        issue_numbers = {d.issue_number for d in markdown_errors}
        assert issue_numbers == {1, 2}
        assert result.posts == ()

    def test_mixed_errors_across_issues_accumulate(self) -> None:
        """Issue 1 has a markdown error, Issue 2 has valid content, Issue 3
        has a front-matter error.  All are reported; posts is empty because
        any error blocks rendering."""

        def bad_renderer(_text: str) -> str:
            raise RuntimeError("boom")

        compiler = BlogCompiler(_make_settings(), markdown_renderer=bad_renderer)
        snap1 = _make_snapshot(number=1, body=_VALID_BODY)
        snap2 = _make_snapshot(
            number=2,
            body=(
                "---\nslug: second\ndescription: d\n"
                'created_date: "2026-01-02"\n---\n\nBody two.'
            ),
        )
        snap3 = _make_snapshot(number=3, body="no front matter")
        result = compiler.compile([snap1, snap2, snap3])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        # Issue 1: markdown render failed
        assert any(
            d.code == "MARKDOWN_RENDER_FAILED" and d.issue_number == 1 for d in errors
        )
        # Issue 2: also markdown render failed (same bad renderer)
        assert any(
            d.code == "MARKDOWN_RENDER_FAILED" and d.issue_number == 2 for d in errors
        )
        # Issue 3: front matter missing
        assert any(
            d.code == "FRONT_MATTER_MISSING" and d.issue_number == 3 for d in errors
        )
        assert result.posts == ()

    def test_collaborator_error_slug_still_participates_in_duplicate_check(
        self,
    ) -> None:
        """A valid slug on an Issue with a collaborator error must still
        participate in SLUG_DUPLICATE checks."""

        def bad_renderer(_text: str) -> str:
            raise RuntimeError("boom")

        compiler = BlogCompiler(_make_settings(), markdown_renderer=bad_renderer)
        snap1 = _make_snapshot(number=1, body=_VALID_BODY)  # slug: my-first-post
        snap2 = _make_snapshot(number=2, body=_VALID_BODY)  # same slug
        result = compiler.compile([snap1, snap2])
        assert result.has_errors
        errors = [d for d in result.diagnostics if d.severity == "error"]
        # Both Issues should have MARKDOWN_RENDER_FAILED
        assert len([d for d in errors if d.code == "MARKDOWN_RENDER_FAILED"]) == 2
        # And SLUG_DUPLICATE should be reported
        assert any(d.code == "SLUG_DUPLICATE" for d in errors)


# ---------------------------------------------------------------------------
# Reserved slug scope clarification (Correctness #6)
# ---------------------------------------------------------------------------


class TestReservedSlugScope:
    """Ticket04 only guards the known ``/blog/page/`` collision as tracer
    scope.  A dynamic RouteRegistry is Ticket18's responsibility.
    """

    def test_reserved_slug_page_rejected_with_clear_message(self) -> None:
        body = '---\nslug: page\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody'
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert result.has_errors
        diag = next(
            d
            for d in result.diagnostics
            if d.code == "SLUG_RESERVED" and d.severity == "error"
        )
        assert diag.issue_number == 1
        assert diag.field == "slug"
        # Message references the reserved route so the author understands why.
        assert "page" in diag.message

    def test_non_page_slug_not_affected_by_reserved_check(self) -> None:
        """Only 'page' is reserved in tracer scope; other slugs are fine."""
        body = (
            '---\nslug: my-post\ndescription: d\ncreated_date: "2026-01-01"\n---\nbody'
        )
        snap = _make_snapshot(body=body)
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        assert not any(d.code == "SLUG_RESERVED" for d in result.diagnostics)


# ---------------------------------------------------------------------------
# End-to-end tracer: compiler -> BlogPost -> render_blog_detail (Architecture #2)
# ---------------------------------------------------------------------------


class TestEndToEndTracer:
    """Independently prove the Ticket04 end-to-end tracer:
    IssueSnapshot -> BlogCompiler -> BlogPost -> canonical route/output path
    -> RenderService.render_blog_detail, for both Escape1 and Escape2.

    This focused integration test writes canonical detail HTML to a tmp
    output directory using ``post.route.output_path``.  It does NOT connect
    to the default CLI pipeline.
    """

    @staticmethod
    def _make_render_settings(theme: str) -> MagicMock:
        project_root = Path(__file__).parent.parent.absolute()
        settings = MagicMock()
        settings.paths.theme_path = project_root / "templates" / theme
        settings.paths.seo_path = project_root / "templates" / "seo"
        settings.paths.theme_url_path = f"/templates/{theme}"
        settings.paths.rss = "atom.xml"
        settings.paths.blog = "blog"
        settings.site.title = "Tracer Blog"
        settings.site.url = "https://example.com"
        settings.site.author = "Author"
        settings.site.description = "Test Description"
        settings.site.language = "en"
        settings.github.username = "user"
        settings.github.repo = "user/repo"
        settings.seo.google_search_console = ""
        settings.profile.avatar = ""
        settings.profile.bio = "Test bio"
        settings.profile.links = []
        settings.site.navigation.items = []
        settings.branding.show_powered_by = True
        settings.branding.powered_by_text = "Powered by"
        settings.branding.powered_by_url = "https://github.com/geoqiao/github-blog"
        settings.branding.show_intro = False
        settings.branding.intro_text = ""
        settings.branding.intro_text2 = ""
        settings.branding.source_link_text = "View Source"
        settings.branding.source_link_url = ""
        settings.comments.provider = "utterances"
        settings.comments.repo = ""
        settings.comments.theme = "github-light"
        settings.comments.theme_mode = "auto"
        return settings

    def test_tracer_escape1_writes_canonical_detail(self, tmp_path: Path) -> None:
        from github_blog.services.render_service import RenderService

        renderer = RenderService(self._make_render_settings("Escape1"))
        snap = _make_snapshot(
            number=42,
            title="Tracer Post",
            body=(
                "---\n"
                "slug: tracer-post\n"
                "description: A tracer post.\n"
                'created_date: "2026-01-05"\n'
                "---\n\n"
                "Hello **world**.\n"
            ),
            labels=("type:blog", "published", "tag:python"),
        )
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        assert len(result.posts) == 1

        post = result.posts[0]
        # Canonical route and output path
        assert post.canonical_path == "/blog/tracer-post/"
        assert post.route.output_path == "blog/tracer-post/index.html"

        # Render and write to tmp output
        html = renderer.render_blog_detail(post)
        output_file = tmp_path / post.route.output_path
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(html, encoding="utf-8")

        # Verify content
        written = output_file.read_text(encoding="utf-8")
        assert "Tracer Post" in written
        assert "/blog/tracer-post/" in written
        assert "42" in written  # issue number for comments
        assert "<strong>world</strong>" in written
        # Front matter must NOT appear in rendered body
        assert "slug:" not in written
        assert "created_date" not in written
        assert "description:" not in written

    def test_tracer_escape2_writes_canonical_detail(self, tmp_path: Path) -> None:
        from github_blog.services.render_service import RenderService

        renderer = RenderService(self._make_render_settings("Escape2"))
        snap = _make_snapshot(
            number=7,
            title="Escape2 Tracer",
            body=(
                "---\n"
                "slug: escape2-tracer\n"
                "description: An Escape2 tracer.\n"
                'created_date: "2026-02-10"\n'
                "---\n\n"
                "Body text here.\n"
            ),
            labels=("type:blog", "published", "tag:rust"),
        )
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        assert len(result.posts) == 1

        post = result.posts[0]
        assert post.canonical_path == "/blog/escape2-tracer/"
        assert post.route.output_path == "blog/escape2-tracer/index.html"

        html = renderer.render_blog_detail(post)
        output_file = tmp_path / post.route.output_path
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(html, encoding="utf-8")

        written = output_file.read_text(encoding="utf-8")
        assert "Escape2 Tracer" in written
        assert "/blog/escape2-tracer/" in written
        assert "7" in written
        assert "Body text here." in written
        # No front matter in body
        assert "slug:" not in written
        assert "created_date" not in written

    def test_tracer_escape1_tag_links_use_strict_path(self, tmp_path: Path) -> None:
        """Strict tracer: Escape1 detail tag hrefs must be /tags/{key}/."""
        from github_blog.services.render_service import RenderService

        renderer = RenderService(self._make_render_settings("Escape1"))
        snap = _make_snapshot(
            number=42,
            title="Tracer Post",
            labels=("type:blog", "published", "tag:python", "tag:rust"),
        )
        result = _make_compiler().compile([snap])
        assert not result.has_errors

        html = renderer.render_blog_detail(result.posts[0])
        assert "/tags/python/" in html
        assert "/tags/rust/" in html
        # Legacy tag paths must NOT appear in strict output
        assert "/tag/python.html" not in html

    def test_tracer_escape2_tag_links_use_strict_path(self, tmp_path: Path) -> None:
        """Strict tracer: Escape2 detail tag hrefs must be /tags/{key}/."""
        from github_blog.services.render_service import RenderService

        renderer = RenderService(self._make_render_settings("Escape2"))
        snap = _make_snapshot(
            number=7,
            title="Escape2 Tracer",
            labels=("type:blog", "published", "tag:rust"),
        )
        result = _make_compiler().compile([snap])
        assert not result.has_errors

        html = renderer.render_blog_detail(result.posts[0])
        assert "/tags/rust/" in html
        # Legacy tag paths must NOT appear in strict output
        assert "/tag/rust.html" not in html


# ---------------------------------------------------------------------------
# BlogTag model: immutable tag value with name and canonical path
# ---------------------------------------------------------------------------


class TestBlogTagModel:
    """BlogPost.tags must contain immutable BlogTag values carrying their
    own display name and canonical path, so templates never decide between
    legacy and strict URL schemes."""

    def test_tags_are_blogtag_objects(self) -> None:
        from github_blog.models.blog_post import BlogTag

        snap = _make_snapshot(
            labels=("type:blog", "published", "tag:python", "tag:rust"),
        )
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        tags = result.posts[0].tags
        assert len(tags) == 2
        assert all(isinstance(t, BlogTag) for t in tags)

    def test_blogtag_carries_name_and_strict_path(self) -> None:
        snap = _make_snapshot(
            labels=("type:blog", "published", "tag:python"),
        )
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        tag = result.posts[0].tags[0]
        assert tag.name == "python"
        assert tag.path == "/tags/python/"

    def test_blogtag_is_frozen(self) -> None:
        import dataclasses

        from github_blog.models.blog_post import BlogTag

        tag = BlogTag(name="python", path="/tags/python/")
        with pytest.raises(dataclasses.FrozenInstanceError):
            tag.name = "changed"  # type: ignore

    def test_no_tags_returns_empty_tuple_of_blogtag(self) -> None:
        snap = _make_snapshot(labels=("type:blog", "published"))
        result = _make_compiler().compile([snap])
        assert not result.has_errors
        assert result.posts[0].tags == ()
