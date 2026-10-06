"""The Config: which repository holds the content and who may publish it.

Only ``github``, ``about`` and ``security`` are read. Every other section of the
file belongs to the site that reads the export, so it is neither read nor
checked. Errors name the field and the reason and never echo the supplied value.
"""

from __future__ import annotations

import difflib
import re
import types
import typing
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    ValidationError,
    field_validator,
    model_validator,
)

from .utils.frontmatter import _StrictYAMLLoader

_ENV_VAR_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


_REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]+$")


class ConfigError(ValueError):
    """One or more Config problems, each naming its field and reason."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("\n".join(problems))


def _validate_repository(value: str) -> str:
    if not _REPOSITORY_PATTERN.fullmatch(value):
        raise ValueError("repository must use the owner/repo format")
    return value


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GithubConfig(_Strict):
    repo: str
    allowed_authors: list[str] = Field(min_length=1)

    @field_validator("repo")
    @classmethod
    def validate_repo(cls, v: str) -> str:
        return _validate_repository(v)

    @field_validator("allowed_authors")
    @classmethod
    def validate_allowed_authors(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        for author in v:
            if not author.strip():
                raise ValueError("allowed_authors must not contain blank entries")
            key = author.strip().casefold()
            if key in seen:
                raise ValueError("allowed_authors lists the same author twice")
            seen.add(key)
        return [author.strip() for author in v]

    @property
    def owner(self) -> str:
        return self.repo.split("/")[0]


class RepositoryIdentity(BaseModel):
    """Verified GitHub.com repository owner; never the workflow actor."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    repository: str
    owner_login: str
    owner_type: Literal["User", "Organization"]

    @field_validator("repository")
    @classmethod
    def validate_repository(cls, value: str) -> str:
        return _validate_repository(value)

    @model_validator(mode="after")
    def coherent_owner(self) -> Self:
        if self.repository.split("/")[0].casefold() != self.owner_login.casefold():
            raise ValueError("repository and owner_login must identify the same owner")
        return self


class AboutConfig(_Strict):
    issue_number: StrictInt | None = Field(default=None, gt=0)


class SecurityConfig(_Strict):
    """The NAME of the token environment variable, never the token."""

    token_env: str = "GITHUB_TOKEN"  # noqa: S105 - environment variable name

    @field_validator("token_env")
    @classmethod
    def validate_token_env(cls, v: str) -> str:
        if not _ENV_VAR_PATTERN.fullmatch(v):
            raise ValueError(
                "token_env must be an environment variable name "
                "(letters, digits and underscores; not starting with a digit)"
            )
        return v


class ContentSettings(BaseModel):
    """The sections that decide which Issues are published.

    ``escaping-site export`` reads only these. Every other section belongs to
    whatever builds the site, so it is neither read nor checked here.
    """

    model_config = ConfigDict(extra="ignore")

    github: GithubConfig
    about: AboutConfig = Field(default_factory=AboutConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)


#: The sections of ``ContentSettings``.
CONTENT_SECTIONS = ("github", "about", "security")


# Only these can be supplied later by resolve_content_settings.
_RESOLVABLE_MISSING = {
    ("github",),
    ("github", "repo"),
    ("github", "allowed_authors"),
}


def read_content_overrides(path: Path) -> dict[str, Any]:
    """Read the Config for an export: only its content sections are checked."""
    data = _load_config(path)
    validate_content_overrides(data)
    return typing.cast(dict[str, Any], data)


def _load_config(path: Path) -> object:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError([f"Config file not found: {path}"]) from None
    try:
        data = yaml.load(text, Loader=_StrictYAMLLoader)  # noqa: S506 - SafeLoader subclass
    except yaml.YAMLError as exc:
        raise ConfigError([_yaml_problem(path, exc)]) from None
    return {} if data is None else data


def _yaml_problem(path: Path, exc: yaml.YAMLError) -> str:
    mark = getattr(exc, "problem_mark", None)
    where = f"{path.name}:{mark.line + 1}:{mark.column + 1}" if mark else path.name
    problem = getattr(exc, "problem", None) or "invalid YAML"
    if "duplicate key" in str(exc).lower():
        problem = "the same key appears twice"
    elif "constructor for the tag" in str(problem):
        problem = "YAML tags such as !!python are not allowed"
    return f"{where}: {problem}"


def validate_content_overrides(data: object) -> None:
    """Validate the content sections; the owner and its authors may come later."""
    if not isinstance(data, dict):
        raise ConfigError(["Config must be a mapping of sections such as github:"])
    content = {name: data[name] for name in CONTENT_SECTIONS if name in data}
    problems = [
        f"{'.'.join(map(str, loc))}: is empty; remove the line or add values under it"
        for loc in _null_locations(content, ())
    ]
    if problems:
        raise ConfigError(problems)
    try:
        ContentSettings.model_validate(content)
    except ValidationError as exc:
        errors = [
            error
            for error in exc.errors()
            if error["type"] != "missing" or error["loc"] not in _RESOLVABLE_MISSING
        ]
        if errors:
            raise ConfigError(
                describe_validation_errors(errors, ContentSettings)
            ) from None


def _null_locations(value: object, loc: tuple[str | int, ...]) -> list[tuple]:
    if value is None:
        return [loc]
    items: list[tuple[str | int, object]] = []
    if isinstance(value, dict):
        items = [(str(key), child) for key, child in value.items()]
    elif isinstance(value, list):
        items = list(enumerate(value))
    return [
        found for key, child in items for found in _null_locations(child, (*loc, key))
    ]


def describe_validation_errors(errors: list[Any], model: type[BaseModel]) -> list[str]:
    """Turn Pydantic errors into ``field: reason`` lines without input values."""
    problems: list[str] = []
    for error in errors:
        if error["type"] == "default_factory_not_called":
            continue  # A consequence of another reported error.
        loc = tuple(error["loc"])
        field = ".".join(map(str, loc)) or "Config"
        if error["type"] == "extra_forbidden":
            known = _fields_at(model, loc[:-1])
            match = difflib.get_close_matches(str(loc[-1]), known, n=1)
            hint = f"; did you mean {match[0]}?" if match else ""
            problems.append(f"{field}: unknown field{hint}")
        elif error["type"] == "missing":
            problems.append(f"{field}: required")
        else:
            message = str(error["msg"]).removeprefix("Value error, ")
            problems.append(f"{field}: {message}")
    return problems


def _fields_at(model: type[BaseModel], loc: tuple[str | int, ...]) -> list[str]:
    current: type[BaseModel] | None = model
    for part in loc:
        if isinstance(part, int) or current is None:
            continue
        field = current.model_fields.get(part)
        current = _model_in(field.annotation) if field is not None else None
    return list(current.model_fields) if current is not None else []


def _model_in(annotation: object) -> type[BaseModel] | None:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    if isinstance(annotation, types.UnionType) or typing.get_origin(annotation):
        for arg in typing.get_args(annotation):
            if found := _model_in(arg):
                return found
    return None


def security_from_config(overrides: dict[str, Any]) -> SecurityConfig:
    """Read only the token variable name from already validated overrides."""
    return SecurityConfig.model_validate(overrides.get("security", {}))
