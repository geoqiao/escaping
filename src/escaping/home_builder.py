from __future__ import annotations

from collections.abc import Sequence

from .models.blog_post import BlogPost
from .models.home_page import HomePage, HomePostEntry
from .routes import RouteRegistry

HOME_POST_COUNT = 5


def _build_home(posts: Sequence[BlogPost], routes: RouteRegistry) -> HomePage:
    """Build Home content; SiteBuilder is the only production caller."""
    recent = sorted(
        posts,
        key=lambda post: (post.published_at, post.issue_number),
        reverse=True,
    )[:HOME_POST_COUNT]
    return HomePage(
        route=routes.home(),
        recent_posts=tuple(
            HomePostEntry(
                issue_number=post.issue_number,
                title=post.title,
                created_date=post.created_date,
                detail_path=post.route.canonical_path,
                tags=post.tags,
            )
            for post in recent
        ),
    )
