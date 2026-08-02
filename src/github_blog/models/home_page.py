"""Immutable Home page models for the Site Compiler.

These are build-time, in-memory values produced by the Home builder. They
contain only plain Python types so no PyGithub object, label interpretation,
YAML parsing, Markdown body, Issue metadata, or auxiliary slug map crosses
into templates or rendering.

The models are sufficient for the Home page (Ticket 06):
``HomePostEntry`` carries a single recent-post summary with pre-computed
detail and tag paths; ``HomeRoute`` maps the canonical ``/`` path to its
``index.html`` output; ``HomePage`` bundles site identity, Site Profile,
navigation, and up to five recent posts so templates
never concatenate URLs or access Issue objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .blog_post import BlogTag


@dataclass(frozen=True)
class HomeRoute:
    """The fixed Home route mapping canonical URL to output path.

    Home always uses ``/`` and writes to ``index.html``.  These are not
    configurable.

    Attributes:
        canonical_path: Canonical URL path, always ``/``.
        output_path: Relative filesystem path, always ``index.html``.
    """

    canonical_path: str
    output_path: str


@dataclass(frozen=True)
class HomeProfileLink:
    """A single link from the Site Profile.

    Attributes:
        name: Display name (e.g. ``GitHub``).
        url: Absolute or relative URL.
    """

    name: str
    url: str


@dataclass(frozen=True)
class HomeProfile:
    """Site Profile data for Home: avatar, short bio, and links.

    All fields are optional (empty string / empty tuple when absent).
    The page remains coherent when profile values are absent.

    Attributes:
        avatar: Avatar URL, empty string when absent.
        bio: Short bio text, empty string when absent.
        links: Tuple of immutable ``HomeProfileLink`` values.
    """

    avatar: str = ""
    bio: str = ""
    links: tuple[HomeProfileLink, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class HomeNavigationLink:
    """A single configured navigation link for Home CTAs.

    Attributes:
        name: Display name (e.g. ``Blog``).
        url: URL path from configured navigation.
    """

    name: str
    url: str


@dataclass(frozen=True)
class HomePostEntry:
    """A single recent-post summary for the Home page.

    All URL paths are pre-computed by the RouteRegistry-backed builder so the
    template never concatenates path segments.

    Attributes:
        issue_number: Immutable GitHub Issue identity for display.
        title: Display title of the post.
        created_date: ``YYYY-MM-DD`` string for display.
        detail_path: Pre-computed canonical URL path to the detail page.
        tags: Tuple of immutable ``BlogTag`` values (name + path).
    """

    issue_number: int
    title: str
    created_date: str
    detail_path: str
    tags: tuple[BlogTag, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class HomePage:
    """Fully resolved Home page ready for rendering.

    Every URL the template needs is pre-computed here: the page's own
    canonical route and per-entry detail and tag paths.  Hero copy comes
    only from site identity, Site Profile, and configured navigation.
    Templates consume only this model and shared context -- no PyGithub
    objects, Issue metadata, labels, or branding.

    Attributes:
        route: Home route (canonical ``/``, output ``index.html``).
        canonical_url: Absolute canonical URL from origin + ``/``.
        site_title: Top-level site title from identity.
        site_author: Display name from identity.
        site_description: Site description from identity.
        profile: Site Profile (avatar, bio, links) -- optional fields.
        navigation: Tuple of configured navigation links.
        recent_posts: Tuple of up to 5 ``HomePostEntry`` values.
    """

    route: HomeRoute
    canonical_url: str
    site_title: str
    site_author: str
    site_description: str
    profile: HomeProfile
    navigation: tuple[HomeNavigationLink, ...] = field(default_factory=tuple)
    recent_posts: tuple[HomePostEntry, ...] = field(default_factory=tuple)
