"""Resolve missing Site Config fields before compilation; no rendering-time I/O."""

from __future__ import annotations

from copy import deepcopy
from typing import Protocol

from pydantic import ValidationError

from .build_result import Diagnostic
from .config import (
    CONTENT_SECTIONS,
    ConfigError,
    ContentSettings,
    PlatformContext,
    ProfileConfig,
    RepositoryIdentity,
    Settings,
    describe_validation_errors,
    validate_config_overrides,
    validate_content_overrides,
)
from .services.github_service import PublicProfile


class SiteInputSource(Protocol):
    def fetch_repository_identity(self, repository: str) -> RepositoryIdentity: ...

    def fetch_public_profile(self, login: str) -> PublicProfile: ...


def resolve_settings(
    overrides: dict,
    *,
    context: PlatformContext | None = None,
    github_service: SiteInputSource | None = None,
    repository_override: str | None = None,
) -> tuple[Settings, tuple[Diagnostic, ...]]:
    """Fill absent fields only, then construct the existing strict Settings.

    Context must be an independently validated GitHub.com/Pages snapshot. It
    never owns filesystem paths. Without it an explicit repository and root URL
    are required; insufficient identity is an error, not an owner.github.io guess.
    """
    validate_config_overrides(overrides)
    data = deepcopy(overrides)
    github = data.setdefault("github", {})
    if repository_override is not None:
        github["repo"] = repository_override
        validate_config_overrides(data)
    site = data.setdefault("site", {})
    profile = data.setdefault("profile", {})
    if context is not None:
        github.setdefault("repo", context.repository)
        site.setdefault("url", str(context.pages_base_url))
    missing = [
        path
        for path, section, key in (
            ("github.repo", github, "repo"),
            ("site.url", site, "url"),
        )
        if key not in section
    ]
    if missing:
        raise ValueError(
            "Missing Config fields (or provide --context): " + ", ".join(missing)
        )

    unset = [
        f"site.{key}" for key in ("title", "author", "description") if key not in site
    ] + [f"profile.{key}" for key in ("avatar", "bio") if key not in profile]
    needs_profile = bool(unset)
    repository = github["repo"]
    identity: RepositoryIdentity | None = context
    cross_repository = (
        context is not None and repository.casefold() != context.repository.casefold()
    )
    if (
        repository_override is not None
        or cross_repository
        or (context is None and (needs_profile or "allowed_authors" not in github))
    ):
        if github_service is None:
            if "allowed_authors" not in github:
                unset.append("github.allowed_authors")
            raise ValueError(
                "reading "
                + (", ".join(unset) or "the repository owner")
                + " from GitHub needs a token; set them in the Config instead, "
                "or provide the token"
            )
        try:
            identity = github_service.fetch_repository_identity(repository)
            if identity.repository.casefold() != repository.casefold():
                raise ValueError("repository mismatch")
        except Exception:
            raise ValueError("Failed to verify github.repo identity") from None
    if "allowed_authors" not in github:
        if identity is None or identity.owner_type != "User":
            raise ValueError(
                "github.allowed_authors must be explicit for an Organization"
            )
        github["allowed_authors"] = [identity.owner_login]

    diagnostics: list[Diagnostic] = []
    if needs_profile:
        if identity is None:
            raise ValueError(
                "Missing trusted owner identity for public Profile defaults"
            )
        login = identity.owner_login
        public = PublicProfile(login)
        try:
            if github_service is None:
                raise ValueError("public profile source unavailable")
            public = github_service.fetch_public_profile(login)
            if public.login.casefold() != login.casefold() or not isinstance(
                public.name, str
            ):
                raise ValueError("invalid public profile")
            ProfileConfig(avatar=public.avatar_url, bio=public.bio)
        except Exception:
            public = PublicProfile(login)
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "PROFILE_ENRICHMENT_FAILED",
                    "Public Profile unavailable; using owner login and empty avatar/bio.",
                    field="profile",
                )
            )
        display_name = public.name.strip() or login
        site.setdefault("title", display_name)
        site.setdefault("author", display_name)
        site.setdefault("description", public.bio)
        profile.setdefault("avatar", public.avatar_url)
        profile.setdefault("bio", public.bio)
    try:
        return Settings.model_validate(data), tuple(diagnostics)
    except ValidationError as exc:
        raise ConfigError(describe_validation_errors(exc.errors(), Settings)) from None


class RepositorySource(Protocol):
    def fetch_repository_identity(self, repository: str) -> RepositoryIdentity: ...


def resolve_content_settings(
    overrides: dict,
    *,
    repository: str | None = None,
    context: RepositoryIdentity | None = None,
    github_service: RepositorySource | None = None,
) -> ContentSettings:
    """The content sections of a Config, for an export.

    ``repository`` replaces ``github.repo``; the context only fills it in. A
    missing ``github.allowed_authors`` is the owner of a personal repository,
    read from the context or from GitHub. Nothing about a site is needed.
    """
    validate_content_overrides(overrides)
    data = {
        name: deepcopy(overrides[name])
        for name in CONTENT_SECTIONS
        if name in overrides
    }
    github = data.setdefault("github", {})
    if repository is not None:
        github["repo"] = repository
        validate_content_overrides(data)
    elif context is not None:
        github.setdefault("repo", context.repository)
    if "repo" not in github:
        raise ValueError("Missing Config field (or pass --repo): github.repo")
    if "allowed_authors" not in github:
        identity = context
        if (
            identity is None
            or identity.repository.casefold() != github["repo"].casefold()
        ):
            if github_service is None:
                raise ValueError(
                    "reading github.allowed_authors from GitHub needs a token; "
                    "set it in the Config instead, or provide the token"
                )
            try:
                identity = github_service.fetch_repository_identity(github["repo"])
            except Exception:
                raise ValueError("Failed to verify github.repo identity") from None
        if identity.owner_type != "User":
            raise ValueError(
                "github.allowed_authors must be explicit for an Organization"
            )
        github["allowed_authors"] = [identity.owner_login]
    try:
        return ContentSettings.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(
            describe_validation_errors(exc.errors(), ContentSettings)
        ) from None
