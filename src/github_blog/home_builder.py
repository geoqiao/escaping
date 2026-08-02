"""Home page builder - the composition seam for Ticket 06.

Takes validated ``BlogPost`` values and explicitly injected ``Settings``,
sorts recent posts by accepted publication ordering (``published_at`` desc
with ``issue_number`` desc tie-breaker), limits to the fixed v1 count of 5,
and produces an immutable ``HomePage`` with every route and link
pre-computed before rendering.

Hero copy and CTAs come only from top-level site identity (title, author,
description, canonical origin), Site Profile (avatar, bio, links), and
configured navigation.  No Markdown body, Issue metadata, labels, or
branding enter the ``HomePage`` model.

The strict SiteModel builder calls this component during every build; the
renderer receives only the resulting ``HomePage`` model.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from .config import Settings
from .models.blog_post import BlogPost
from .models.home_page import (
    HomeNavigationLink,
    HomePage,
    HomePostEntry,
    HomeProfile,
    HomeProfileLink,
    HomeRoute,
)

#: Home recent Blog count is fixed at 5 for v1 (not configurable).
HOME_POST_COUNT: int = 5

#: Fixed Home route: canonical ``/`` -> output ``index.html``.
_HOME_ROUTE = HomeRoute(canonical_path="/", output_path="index.html")


class HomeBuilder:
    """Build a strict ``HomePage`` from validated ``BlogPost`` values.

    The builder is the composition seam: validated posts and settings go
    in, a ``HomePage`` comes out.  No PyGithub object, label
    interpretation, Markdown body, or branding crosses this seam.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, posts: Sequence[BlogPost]) -> HomePage:
        """Build a ``HomePage`` with at most 5 recent posts.

        Posts sort by GitHub publication timestamp (``published_at``)
        descending, with Issue number descending as the tie-breaker.
        """
        sorted_posts = sorted(
            posts,
            key=lambda post: (post.published_at, post.issue_number),
            reverse=True,
        )
        recent = sorted_posts[:HOME_POST_COUNT]

        return HomePage(
            route=_HOME_ROUTE,
            canonical_url=_absolute_url(self._settings, "/"),
            site_title=self._settings.site.title,
            site_author=self._settings.site.author,
            site_description=self._settings.site.description,
            profile=self._build_profile(),
            navigation=self._build_navigation(),
            recent_posts=tuple(
                HomePostEntry(
                    title=post.title,
                    created_date=post.created_date,
                    detail_path=post.canonical_path,
                    tags=post.tags,
                )
                for post in recent
            ),
        )

    def _build_profile(self) -> HomeProfile:
        return HomeProfile(
            avatar=self._settings.profile.avatar,
            bio=self._settings.profile.bio,
            links=tuple(
                HomeProfileLink(name=link.name, url=link.url)
                for link in self._settings.profile.links
            ),
        )

    def _build_navigation(self) -> tuple[HomeNavigationLink, ...]:
        return tuple(
            HomeNavigationLink(name=item.name, url=item.url)
            for item in self._settings.site.navigation.items
        )


def _absolute_url(settings: Settings, canonical_path: str) -> str:
    """Join the configured HTTPS origin and a pre-computed absolute path."""
    return f"{str(settings.site.url).rstrip('/')}{canonical_path}"


def write_home_page(
    home: HomePage,
    render_html: Callable[[HomePage], str],
    output_dir: Path,
) -> tuple[Path, ...]:
    """Write a strict Home page to its pre-computed output path.

    This focused writer remains useful for component tests. It writes the
    rendered page beneath ``output_dir`` using the model route.
    """
    path = output_dir / home.route.output_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(home), encoding="utf-8")
    return (path,)
