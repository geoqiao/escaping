from __future__ import annotations

from datetime import datetime, timezone

import pytest

from github_blog.config import Settings
from github_blog.content_compiler import ContentCompiler
from github_blog.models.content import ContentCompilationResult
from github_blog.models.issue_snapshot import IssueSnapshot

_NOW = datetime(2026, 1, 10, tzinfo=timezone.utc)


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


def test_compiles_blog_idea_and_configured_about_once() -> None:
    result = ContentCompiler(_settings()).compile(
        [_snapshot(1, "blog"), _snapshot(2, "idea"), _snapshot(10, "about")]
    )

    assert not result.has_errors
    assert result.blogs[0].canonical_path == "/blog/test-post/"
    assert result.ideas[0].canonical_path == "/ideas/2/"
    assert result.about is not None and result.about.canonical_path == "/about/"
    assert "description:" not in result.ideas[0].body_html
    assert "<script" not in result.ideas[0].body_html


def test_ideas_forbid_slug_sort_and_keep_tags_outside_blog_taxonomy() -> None:
    older = _NOW.replace(day=8)
    result = ContentCompiler(_settings()).compile(
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

    invalid = ContentCompiler(_settings()).compile(
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
    result = ContentCompiler(_settings()).compile(snapshots)
    assert expected in _codes(result)
    assert result.about is None


def test_missing_about_and_about_tags_fail() -> None:
    missing = ContentCompiler(_settings()).compile([_snapshot(1, "blog")])
    assert "ABOUT_MISSING" in _codes(missing)

    tagged = ContentCompiler(_settings()).compile(
        [_snapshot(10, "about", labels=("tag:profile",))]
    )
    assert "ABOUT_TAG_FORBIDDEN" in _codes(tagged)
