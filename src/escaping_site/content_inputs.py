"""Fill in what the Config leaves out, before any Issue is read."""

from __future__ import annotations

from copy import deepcopy
from typing import Protocol

from pydantic import ValidationError

from .config import (
    CONTENT_SECTIONS,
    ConfigError,
    ContentSettings,
    RepositoryIdentity,
    describe_validation_errors,
    validate_content_overrides,
)


class RepositorySource(Protocol):
    def fetch_repository_identity(self, repository: str) -> RepositoryIdentity: ...


def resolve_content_settings(
    overrides: dict,
    *,
    repository: str | None = None,
    github_service: RepositorySource | None = None,
) -> ContentSettings:
    """The Config with its gaps filled in.

    ``repository`` replaces ``github.repo``. A missing
    ``github.allowed_authors`` is the owner of a personal repository, read
    from GitHub.
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
    if "repo" not in github:
        raise ValueError("Missing Config field (or pass --repo): github.repo")
    if "allowed_authors" not in github:
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
