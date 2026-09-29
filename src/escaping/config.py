"""Site Config: the site layer shared by every Theme, plus the Theme selection.

A value belongs here when it still means something after switching Themes.
Presentation choices are Theme options: ``theme.options`` is kept as raw data
and validated against the selected Theme's ``theme.yaml`` (see ``theme.py``).

All models reject unknown fields. Errors name the field and the reason and
never echo the supplied value.
"""

from __future__ import annotations

import difflib
import json
import re
import types
import typing
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Self
from urllib.parse import unquote, urlparse, urlunparse

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StrictBool,
    StrictInt,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

from .atom_feed import NOT_XML
from .remote_theme import PREFIX as REMOTE_THEME_PREFIX
from .remote_theme import RemoteTheme
from .routes import SITE_PATH, SLUG, Sections
from .utils.frontmatter import _StrictYAMLLoader

_ENV_VAR_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]+$")
_BUILTIN_THEME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
_SECTION_PATH = re.compile(r"^/(?:[a-z0-9-]+/)+$")
_EXTRA_PATH = re.compile(r"^/(?:[a-z0-9-]+/|\{slug\}/)+$")
#: Sections in navigation order; the first three own every address below them.
_SECTIONS = ("blog", "ideas", "tags", "projects", "about")
_PREFIX_SECTIONS = ("blog", "ideas", "tags")
_ASSETS = "/assets/"
_UNSAFE_PATH_CHARS = re.compile(r"[\x00-\x20\x7f-\x9f\\?#\u2028\u2029\ufeff]")


class ConfigError(ValueError):
    """One or more Config problems, each naming its field and reason."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("\n".join(problems))


def _validate_repository(value: str) -> str:
    if not _REPOSITORY_PATTERN.fullmatch(value):
        raise ValueError("repository must use the owner/repo format")
    return value


def validate_safe_href(value: str) -> str:
    """Accept HTTPS, mailto:, root-relative and fragment links only."""
    if (
        not value
        or "\\" in value
        or any(
            char.isspace() or ord(char) < 32 or 0x7F <= ord(char) <= 0x9F
            for char in value
        )
    ):
        raise ValueError("link URL contains whitespace, a backslash, or control data")

    if value.startswith("#"):
        if len(value) == 1:
            raise ValueError("link fragment must not be empty")
        return value

    parsed = urlparse(value)
    if value.startswith("/"):
        if value.startswith("//") or parsed.scheme or parsed.netloc:
            raise ValueError("protocol-relative links are not allowed")
        return value

    if parsed.scheme == "https" and parsed.hostname:
        if parsed.username or parsed.password:
            raise ValueError("HTTPS links must not contain userinfo")
        return value

    if parsed.scheme == "mailto" and parsed.path and not parsed.netloc:
        return value

    raise ValueError("link URL must be HTTPS, mailto, root-relative, or a fragment")


def validate_safe_resource_url(value: str) -> str:
    """Accept an empty value, an HTTPS URL or a root-relative path."""
    if not value:
        return value
    validated = validate_safe_href(value)
    if validated.startswith("#") or urlparse(validated).scheme == "mailto":
        raise ValueError("resource URL must be HTTPS or root-relative")
    return validated


def _site_url(value: object) -> str:
    """An HTTPS site address, at the root or under a path, ending with /."""
    if isinstance(value, HttpUrl):
        value = str(value)
    if not isinstance(value, str):
        raise ValueError("site URL must be a string")
    validate_safe_href(value)
    parsed = urlparse(value)
    if parsed.scheme != "https":
        raise ValueError("site URL must use HTTPS")
    if parsed.username or parsed.password:
        raise ValueError("site URL must not contain userinfo")
    if parsed.query or parsed.fragment or parsed.params:
        raise ValueError("site URL must not contain a query or fragment")
    path = parsed.path.rstrip("/") + "/"
    if not SITE_PATH.fullmatch(path):
        raise ValueError(
            "site URL must be like https://example.com/ or "
            "https://example.com/notes/; each part of the path may use "
            "letters, digits, '.', '_', '~' and '-'"
        )
    return urlunparse(("https", parsed.netloc, path, "", "", ""))


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


class Link(_Strict):
    """A named link whose destination cannot execute script."""

    name: str
    url: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("link name must not be blank")
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return validate_safe_href(v)


def default_navigation(sections: Sections) -> list[Link]:
    """Home, Blog, then Projects, Tags and About when they are on, then RSS."""
    items = [("Home", "/"), ("Blog", sections.blog)]
    items += [
        (name.title(), path)
        for name in ("projects", "tags", "about")
        if (path := getattr(sections, name))
    ]
    return [Link(name=name, url=url) for name, url in (*items, ("RSS", "/atom.xml"))]


class NavigationConfig(_Strict):
    """``items`` left out means the default for the pages that are on."""

    items: list[Link] | None = None


class SiteConfig(_Strict):
    title: str
    author: str
    url: HttpUrl
    description: str = ""
    language: str = "en"
    navigation: NavigationConfig = Field(default_factory=NavigationConfig)

    @field_validator("title", "author", "description")
    @classmethod
    def validate_feed_text(cls, v: str) -> str:
        if match := NOT_XML.search(v):
            raise ValueError(
                f"contains U+{ord(match.group()):04X}, a character the Atom feed "
                "cannot hold"
            )
        return v

    @field_validator("url", mode="before")
    @classmethod
    def validate_site_url(cls, v: object) -> str:
        return _site_url(v)

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", v):
            raise ValueError("language must be a language tag such as en or zh-CN")
        return v


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


class PlatformContext(RepositoryIdentity):
    """Non-secret platform snapshot supplied by the Action, not another Config."""

    pages_base_url: HttpUrl

    @field_validator("pages_base_url", mode="before")
    @classmethod
    def validate_pages_url(cls, value: object) -> str:
        return _site_url(value)


class ProfileConfig(_Strict):
    """Site Profile; the About narrative belongs to the About Issue."""

    avatar: str = ""
    bio: str = ""
    links: list[Link] = Field(default_factory=list)

    @field_validator("avatar")
    @classmethod
    def validate_avatar(cls, v: str) -> str:
        return validate_safe_resource_url(v)


class AboutConfig(_Strict):
    issue_number: StrictInt | None = Field(default=None, gt=0)


class PathsConfig(_Strict):
    output: str = "output"
    page_size: StrictInt = Field(default=10, gt=0)


def _section_path(value: object, name: str) -> str | None:
    default = getattr(Sections(), name)
    if value is True:
        return default
    if value is False:
        if name == "blog":
            raise ValueError("the Blog cannot be turned off")
        return None
    if not isinstance(value, str) or not _SECTION_PATH.fullmatch(value):
        off = "" if name == "blog" else ", or false to turn the page off"
        raise ValueError(
            f"use a path of lowercase segments ending with /, like {default}{off}"
        )
    if value.startswith(_ASSETS):
        raise ValueError(f"{_ASSETS} is reserved for static files")
    return value


class ExtraPageConfig(_Strict):
    """A page the Theme renders with its own template, once or per project."""

    path: str
    template: str
    for_each: Literal["projects"] | None = None

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        if not _EXTRA_PATH.fullmatch(v):
            raise ValueError("use lowercase segments ending with /, like /now/")
        if v.startswith(_ASSETS):
            raise ValueError(f"{_ASSETS} is reserved for static files")
        return v

    @field_validator("template")
    @classmethod
    def validate_template(cls, v: str) -> str:
        template = PurePosixPath(v)
        if (
            template.is_absolute()
            or ".." in template.parts
            or "\\" in v
            or template.suffix != ".html"
        ):
            raise ValueError("use a template file name in the Theme, like now.html")
        return v

    @model_validator(mode="after")
    def slug_with_for_each(self) -> Self:
        per_project = self.for_each == "projects"
        if (self.path.count("{slug}") == 1) != per_project:
            raise ValueError(
                "use {slug} in path exactly once with for_each: projects, "
                "and not otherwise"
            )
        if "{slug}" in self.template and not per_project:
            raise ValueError("template may use {slug} only with for_each: projects")
        return self

    def path_for(self, slug: str | None) -> str:
        return self.path.replace("{slug}", slug) if slug else self.path

    def template_for(self, slug: str | None) -> str:
        return self.template.replace("{slug}", slug) if slug else self.template


class PagesConfig(_Strict):
    """Which pages the site has and where. Home is always ``/``.

    A section is a path such as ``/notes/``, ``true`` for its default path, or
    ``false`` to turn it off. The Blog cannot be turned off.
    """

    blog: str = "/blog/"
    ideas: str | None = "/ideas/"
    tags: str | None = "/tags/"
    projects: str | None = "/projects/"
    about: str | None = "/about/"
    extra: list[ExtraPageConfig] = Field(default_factory=list)

    @field_validator(*_SECTIONS, mode="before")
    @classmethod
    def validate_section(cls, v: object, info: ValidationInfo) -> str | None:
        return _section_path(v, str(info.field_name))

    @model_validator(mode="after")
    def distinct_paths(self) -> Self:
        sections = [(name, getattr(self, name)) for name in _SECTIONS]
        on = [(name, path) for name, path in sections if path]
        problems = []
        for index, (name, path) in enumerate(on):
            for other, other_path in on[index + 1 :]:
                if path == other_path:
                    problems.append(f"{name} and {other} use the same path {path}")
                elif other_path.startswith(path) or path.startswith(other_path):
                    problems.append(
                        f"{name} ({path}) and {other} ({other_path}) must not be "
                        "inside each other"
                    )
        seen: set[str] = set()
        for index, page in enumerate(self.extra):
            where = f"extra.{index}.path {page.path}"
            if page.path in seen:
                problems.append(f"{where} is listed twice")
            seen.add(page.path)
            for name, path in on:
                if page.path == path:
                    problems.append(f"{where} is already the {name} page")
                elif name in _PREFIX_SECTIONS and page.path.startswith(path):
                    problems.append(
                        f"{where} is inside {name} ({path}), which owns every "
                        "address below it"
                    )
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def sections(self) -> Sections:
        return Sections(
            blog=self.blog,
            ideas=self.ideas,
            tags=self.tags,
            projects=self.projects,
            about=self.about,
        )


def _site_path(value: str, *, source: bool) -> str:
    """A decoded, NFC path of this site; a source must name one HTML file."""
    try:
        path = unicodedata.normalize("NFC", unquote(value, errors="strict"))
    except UnicodeDecodeError:
        raise ValueError("a redirect address has an invalid %-escape") from None
    parts = path.split("/")
    if (
        not path.startswith("/")
        or path.startswith("//")
        or _UNSAFE_PATH_CHARS.search(path)
        or any(part in (".", "..") for part in parts)
        or "" in parts[1:-1]
    ):
        raise ValueError(
            "use a path of this site such as /blog/old-post/, without spaces, ? or #"
        )
    if not source:
        return path
    if path in ("/", "/index.html", "/404.html"):
        raise ValueError(f"{path} cannot redirect")
    if path.startswith(_ASSETS):
        raise ValueError(f"{_ASSETS} is reserved for static files")
    if not path.endswith(("/", ".html")):
        raise ValueError(
            "end the old address with / (it then covers /old and /old/) or .html"
        )
    return path


def _check_redirects(value: dict[str, str]) -> dict[str, str]:
    redirects: dict[str, str] = {}
    folded: set[str] = set()
    for old, new in value.items():
        source = _site_path(old, source=True)
        if source.casefold() in folded:
            raise ValueError(f"{source} is listed twice (addresses ignore case here)")
        folded.add(source.casefold())
        redirects[source] = _site_path(new, source=False)
    for start in redirects:
        seen = [start]
        while (target := redirects.get(seen[-1])) is not None:
            if target in seen:
                raise ValueError(f"{start} redirects in a circle")
            seen.append(target)
    return redirects


class ThemeConfig(_Strict):
    """``use`` is a built-in name, ``github.com/OWNER/REPO[/FOLDER]@VERSION``
    or a Config-relative directory (any other value with ``/``)."""

    use: str = "quiet"
    options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("use")
    @classmethod
    def validate_use(cls, v: str) -> str:
        if v.startswith(REMOTE_THEME_PREFIX):
            RemoteTheme.parse(v)
            return v
        if "/" not in v:
            if not _BUILTIN_THEME_PATTERN.fullmatch(v):
                raise ValueError(
                    "use a built-in Theme name such as quiet, a directory path "
                    "such as ./theme, or github.com/OWNER/REPOSITORY/FOLDER@VERSION"
                )
            return v
        path = PurePosixPath(v)
        if path.is_absolute() or ".." in path.parts or "\\" in v:
            raise ValueError("a local Theme path must stay inside the site repository")
        return v


class CommentsConfig(_Strict):
    """Utterances comments; ``repo`` falls back to ``github.repo`` when empty."""

    enabled: StrictBool = False
    repo: str = ""

    @field_validator("repo")
    @classmethod
    def validate_repo(cls, v: str) -> str:
        return _validate_repository(v) if v else v


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


class SeoConfig(_Strict):
    google_search_console: str = ""
    social_image: str = ""
    social_image_alt: str = ""

    @field_validator("social_image")
    @classmethod
    def validate_social_image(cls, v: str) -> str:
        return validate_safe_resource_url(v)


class ProjectFallbackMetadata(_Strict):
    """Values used when GitHub repository metadata cannot be read."""

    stars: StrictInt | None = Field(default=None, ge=0)
    forks: StrictInt | None = Field(default=None, ge=0)
    language: str | None = None
    topics: list[str] | None = None


def _default_project_slug(data: dict[str, Any]) -> str:
    repository = data.get("repository")
    if not isinstance(repository, str) or not repository:
        return ""
    name = repository.rsplit("/", 1)[-1].casefold()
    return re.sub(r"[^a-z0-9]+", "-", name).strip("-")


def _default_project_title(data: dict[str, Any]) -> str:
    repository = data.get("repository")
    if not isinstance(repository, str):
        return ""
    return repository.rsplit("/", 1)[-1]


class ProjectCatalogEntry(_Strict):
    """A curated project: a public repository, a website, or both.

    ``slug`` defaults to the repository name in kebab case. Explicit
    ``title``/``summary`` win over repository metadata, including empty values.
    """

    repository: str = ""
    website: str = ""
    slug: str = Field(default_factory=_default_project_slug)
    title: str = Field(default_factory=_default_project_title)
    summary: str = ""
    featured: StrictBool = False
    order: StrictInt = 0
    fallback_metadata: ProjectFallbackMetadata | None = None
    image: str = ""
    links: list[Link] = Field(default_factory=list)

    @field_validator("repository")
    @classmethod
    def validate_repository(cls, v: str) -> str:
        return _validate_repository(v) if v else v

    @field_validator("website")
    @classmethod
    def validate_website(cls, v: str) -> str:
        if v and urlparse(validate_safe_href(v)).scheme != "https":
            raise ValueError("website must be an HTTPS URL")
        return v

    @field_validator("image")
    @classmethod
    def validate_image(cls, v: str) -> str:
        return validate_safe_resource_url(v)

    @model_validator(mode="after")
    def require_identity(self) -> Self:
        if not self.repository and not self.website:
            raise ValueError("a project needs a repository, a website, or both")
        if not SLUG.fullmatch(self.slug):
            raise ValueError(
                "slug must use lowercase letters, digits and single hyphens"
                if self.slug or self.repository
                else "a project without a repository needs a slug"
            )
        if not self.title.strip():
            raise ValueError("a project without a repository needs a title")
        return self


class Settings(_Strict):
    """Complete Site Config, explicitly injected; never a global singleton."""

    github: GithubConfig
    site: SiteConfig
    profile: ProfileConfig = Field(default_factory=ProfileConfig)
    about: AboutConfig = Field(default_factory=AboutConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    pages: PagesConfig = Field(default_factory=PagesConfig)
    theme: ThemeConfig = Field(default_factory=ThemeConfig)
    seo: SeoConfig = Field(default_factory=SeoConfig)
    comments: CommentsConfig = Field(default_factory=CommentsConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    projects: list[ProjectCatalogEntry] = Field(default_factory=list)
    #: Old address -> the page it moved to; see ``_check_redirects``.
    redirects: dict[str, str] = Field(default_factory=dict)

    @field_validator("redirects")
    @classmethod
    def validate_redirects(cls, v: dict[str, str]) -> dict[str, str]:
        return _check_redirects(v)

    @field_validator("projects")
    @classmethod
    def unique_project_slugs(
        cls, v: list[ProjectCatalogEntry]
    ) -> list[ProjectCatalogEntry]:
        slugs = [project.slug for project in v]
        duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
        if duplicates:
            raise ValueError(
                f"projects share the slug {', '.join(duplicates)}; "
                "set a distinct slug for each"
            )
        return v

    @model_validator(mode="after")
    def about_page_on(self) -> Self:
        if self.about.issue_number is not None and self.pages.about is None:
            raise ValueError(
                "about.issue_number is set but pages.about is false; remove one of them"
            )
        return self

    @property
    def navigation(self) -> list[Link]:
        """The configured navigation, or the default for the pages that are on."""
        items = self.site.navigation.items
        return items if items is not None else default_navigation(self.pages.sections())


# Only these identities can be supplied later by resolve_settings.
_RESOLVABLE_MISSING = {
    ("github",),
    ("github", "repo"),
    ("github", "allowed_authors"),
    ("site",),
    ("site", "title"),
    ("site", "author"),
    ("site", "url"),
}


def read_config_overrides(path: Path) -> dict[str, Any]:
    """Read and validate the Site Config file; an empty file means ``{}``."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError([f"Config file not found: {path}"]) from None
    try:
        data = yaml.load(text, Loader=_StrictYAMLLoader)  # noqa: S506 - SafeLoader subclass
    except yaml.YAMLError as exc:
        raise ConfigError([_yaml_problem(path, exc)]) from None
    if data is None:
        data = {}
    validate_config_overrides(data)
    return data


def _yaml_problem(path: Path, exc: yaml.YAMLError) -> str:
    mark = getattr(exc, "problem_mark", None)
    where = f"{path.name}:{mark.line + 1}:{mark.column + 1}" if mark else path.name
    problem = getattr(exc, "problem", None) or "invalid YAML"
    if "duplicate key" in str(exc).lower():
        problem = "the same key appears twice"
    elif "constructor for the tag" in str(problem):
        problem = "YAML tags such as !!python are not allowed"
    return f"{where}: {problem}"


def validate_config_overrides(data: object) -> None:
    """Validate supplied fields, deferring only resolvable missing identities."""
    if not isinstance(data, dict):
        raise ConfigError(["Config must be a mapping of sections such as site:"])
    problems = [
        f"{'.'.join(map(str, loc))}: is empty; remove the line or add values under it"
        for loc in _null_locations(data, ())
    ]
    if problems:
        raise ConfigError(problems)
    try:
        Settings.model_validate(data)
    except ValidationError as exc:
        errors = [
            error
            for error in exc.errors()
            if error["type"] != "missing" or error["loc"] not in _RESOLVABLE_MISSING
        ]
        if errors:
            raise ConfigError(describe_validation_errors(errors, Settings)) from None


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


def read_platform_context(path: Path) -> PlatformContext:
    """Validate every explicitly provided platform field, even with full Config."""

    def unique_keys(pairs: list[tuple[str, object]]) -> dict:
        result: dict = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Context JSON must have unique fields")
            result[key] = value
        return result

    try:
        data = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys
        )
        return PlatformContext.model_validate(data)
    except ValidationError as exc:
        problems = describe_validation_errors(exc.errors(), PlatformContext)
        raise ConfigError(
            [f"{path.name}: {p.removeprefix('Config: ')}" for p in problems]
        ) from None
    except ValueError as exc:
        raise ConfigError([f"{path.name}: {exc}"]) from None


def security_from_config(overrides: dict[str, Any]) -> SecurityConfig:
    """Read only the token variable name from already validated overrides."""
    return SecurityConfig.model_validate(overrides.get("security", {}))
