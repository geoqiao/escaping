from __future__ import annotations

from collections.abc import Sequence

from .models.blog_post import BlogPost, blog_post_sort_key
from .models.home_page import HomePage, HomePostEntry
from .routes import RouteRegistry

HOME_POST_COUNT = 5


def build_home(
    posts: Sequence[BlogPost],
    routes: RouteRegistry,
    featured_posts: Sequence[int] = (),
) -> HomePage:
    """Build Home content; SiteBuilder is the only production caller."""
    recent = sorted(
        posts,
        key=blog_post_sort_key,
        reverse=True,
    )[:HOME_POST_COUNT]
    entries = {
        post.issue_number: HomePostEntry(
            issue_number=post.issue_number,
            title=post.title,
            description=post.description,
            created_date=post.created_date,
            detail_path=post.route.canonical_path,
            tags=post.tags,
        )
        for post in posts
    }
    missing = [number for number in featured_posts if number not in entries]
    if missing:
        raise ValueError(f"Featured Issues must be published Blog content: {missing}")
    return HomePage(
        route=routes.home(),
        recent_posts=tuple(entries[post.issue_number] for post in recent),
        featured_posts=tuple(entries[number] for number in featured_posts),
    )
