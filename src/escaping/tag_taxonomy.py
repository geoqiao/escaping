from __future__ import annotations

from collections.abc import Sequence

from .models.blog_post import BlogPost, blog_post_sort_key
from .models.tag_taxonomy import Tag, TagTaxonomyResult


def build_tag_taxonomy(posts: Sequence[BlogPost]) -> TagTaxonomyResult:
    """Group Blog posts by tag key; the newest post's spelling names the tag."""
    grouped: dict[str, list[BlogPost]] = {}
    for post in sorted(posts, key=blog_post_sort_key, reverse=True):
        for tag in post.tags:
            grouped.setdefault(tag.key, []).append(post)
    tags = []
    for key in sorted(grouped):
        members = grouped[key]
        first = next(tag for tag in members[0].tags if tag.key == key)
        tags.append(Tag(first.name, key, first.route, tuple(members)))
    return TagTaxonomyResult(tags=tuple(tags))
