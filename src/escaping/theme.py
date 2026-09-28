"""Theme API 3: load a Theme directory, its built-in parent, options and strings.

A Theme is templates, static files and ``theme.yaml``. Loading never touches
the network and never executes Theme code. See docs/themes/authoring.md.
"""

from __future__ import annotations

import difflib
import os
import re
import shutil
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any, Literal

import yaml
from jinja2 import (
    BaseLoader,
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    PrefixLoader,
    StrictUndefined,
    TemplateError,
    TemplateSyntaxError,
)
from pydantic import BaseModel, ConfigDict, StrictInt, ValidationError

from .config import ConfigError, describe_validation_errors, validate_safe_href
from .utils.frontmatter import _StrictYAMLLoader

THEME_API = 3
BUILTIN_THEMES = Path(__file__).parent / "themes"

#: Templates the compiler renders; every Theme (or its parent) provides them.
PAGE_TEMPLATES = (
    "home.html",
    "blog.html",
    "post.html",
    "ideas.html",
    "idea.html",
    "about.html",
    "projects.html",
    "tags.html",
    "tag.html",
)
#: Rendered to ``404.html`` when present.
NOT_FOUND_TEMPLATE = "404.html"
#: Static files under this directory name are published by the compiler.
SHARED_ASSET_DIR = "escaping"

_OPTION_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_STRING_KEY = re.compile(r"^[a-z][a-z0-9_]*$")
_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_PAGE_PATH = re.compile(r"^/(?:[a-z0-9-]+/|\{slug\}/)+$")
_COMPILER_PATHS = ("/", "/blog/", "/ideas/", "/about/", "/projects/", "/tags/")
_COMPILER_PREFIXES = ("/blog/", "/ideas/", "/tags/", "/assets/")
_RESERVED_STRING_KEYS = frozenset({"language"})

OptionType = Literal[
    "string", "boolean", "integer", "color", "url", "choice", "list", "posts"
]


class ThemeError(ConfigError):
    """A Theme cannot be loaded, or the site's options do not fit it."""


class _OptionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: OptionType
    default: Any
    values: list[str] | None = None
    description: str = ""


class _PageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    template: str
    for_each: Literal["projects"] | None = None


class _ManifestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api: StrictInt
    extends: str | None = None
    options: dict[str, _OptionModel] = {}
    pages: list[_PageModel] = []
    strings: dict[str, dict[str, str]] = {}


@dataclass(frozen=True)
class OptionSpec:
    type: OptionType
    default: object
    values: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class PageSpec:
    path: str
    template: str
    for_each: Literal["projects"] | None = None

    def template_for(self, slug: str | None) -> str:
        return self.template.replace("{slug}", slug) if slug else self.template

    def path_for(self, slug: str | None) -> str:
        return self.path.replace("{slug}", slug) if slug else self.path


@dataclass(frozen=True)
class ThemeLayer:
    name: str
    root: Path


@dataclass(frozen=True)
class LoadedTheme:
    """A Theme merged with its parent: most specific layer first."""

    name: str
    layers: tuple[ThemeLayer, ...]
    options: Mapping[str, OptionSpec]
    pages: tuple[PageSpec, ...]
    strings: Mapping[str, Mapping[str, str]]

    @property
    def local_roots(self) -> tuple[Path, ...]:
        return tuple(
            layer.root
            for layer in self.layers
            if not layer.root.is_relative_to(BUILTIN_THEMES)
        )

    def environment(self) -> Environment:
        loaders: list[BaseLoader] = [
            FileSystemLoader(str(layer.root)) for layer in self.layers
        ]
        loaders.extend(
            PrefixLoader({f"@{layer.name}": FileSystemLoader(str(layer.root))})
            for layer in self.layers[1:]
        )
        return Environment(
            loader=ChoiceLoader(loaders), autoescape=True, undefined=StrictUndefined
        )

    def has_template(self, name: str) -> bool:
        return any((layer.root / name).is_file() for layer in self.layers)

    def check(self, project_slugs: Iterable[str] = ()) -> None:
        """Fail before any network access if a template is missing or invalid."""
        problems = [
            f"{self.name}: missing template {name}"
            for name in PAGE_TEMPLATES
            if not self.has_template(name)
        ]
        slugs = tuple(project_slugs)
        for page in self.pages:
            for slug in slugs if page.for_each else (None,):
                template = page.template_for(slug)
                if not self.has_template(template):
                    problems.append(
                        f"{self.name}: page {page.path_for(slug)} needs template "
                        f"{template}"
                    )
        environment = self.environment()
        for name in environment.list_templates(filter_func=_is_template):
            try:
                environment.get_template(name)
            except TemplateSyntaxError as exc:
                problems.append(
                    f"{self.name}: {exc.name or name} line {exc.lineno}: {exc.message}"
                )
            except TemplateError as exc:
                problems.append(f"{self.name}: {name}: {exc}")
        if problems:
            raise ThemeError(problems)

    def resolve_options(self, values: Mapping[str, object]) -> SimpleNamespace:
        """Apply defaults and check every configured value against its type."""
        problems = []
        for name in values:
            if name not in self.options:
                match = difflib.get_close_matches(name, list(self.options), n=1)
                hint = f"; did you mean {match[0]}?" if match else ""
                problems.append(
                    f"theme.options.{name}: {self.name} has no such option{hint}"
                )
        resolved: dict[str, object] = {}
        for name, spec in self.options.items():
            try:
                resolved[name] = _check_value(spec, values.get(name, spec.default))
            except ValueError as exc:
                problems.append(f"theme.options.{name}: {exc}")
        if problems:
            raise ThemeError(problems)
        return SimpleNamespace(**resolved)

    def strings_for(self, language: str) -> SimpleNamespace:
        """UI strings: English, overlaid by the primary subtag, then the full tag."""
        tag = language.casefold()
        chain = ["en", tag.split("-")[0], tag]
        table: dict[str, str] = {}
        used = "en"
        for code in dict.fromkeys(chain):
            if code in self.strings:
                table.update(self.strings[code])
                used = code
        return SimpleNamespace(language=used, **table)

    def static_files(self) -> dict[str, Path]:
        """Published path under ``/assets/`` -> source file; child files win."""
        files: dict[str, Path] = {}
        for layer in reversed(self.layers):
            static = layer.root / "static"
            if static.is_dir():
                for path in sorted(static.rglob("*")):
                    relative = path.relative_to(static)
                    if path.is_file() and not any(
                        part.startswith(".") for part in relative.parts
                    ):
                        files[relative.as_posix()] = path
        return files

    def copy_static(self, output_dir: Path) -> None:
        assets = output_dir / "assets"
        for relative, source in self.static_files().items():
            target = assets / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)


def _is_template(name: str) -> bool:
    # ``@parent/...`` names repeat the parent's own files; built-ins are tested.
    return (
        name.endswith(".html")
        and not name.startswith("@")
        and name.split("/", 1)[0] != "static"
    )


class ThemeLoader:
    """Load a built-in or Config-relative Theme without network I/O."""

    def __init__(self, config_root: Path) -> None:
        if not config_root.is_absolute():
            raise ValueError("ThemeLoader config_root must be absolute")
        self.config_root = config_root

    def load(self, use: str) -> LoadedTheme:
        if "/" in use:
            relative = Path(use)
            root = self.config_root / relative
            current = self.config_root
            for part in relative.parts:
                current = current / part
                if current.is_symlink():
                    raise ThemeError([f"theme.use: {use} is a symbolic link"])
            if not root.is_dir():
                raise ThemeError([f"theme.use: directory {use} does not exist"])
            # ``use`` contains "/", so a local layer never shadows a built-in.
            layers = self._layers(use, root.resolve(), seen=())
            name = root.resolve().name
        else:
            layers = self._builtin(use, seen=())
            name = use
        return _merge(name, layers)

    def _builtin(
        self, name: str, *, seen: tuple[str, ...]
    ) -> list[tuple[ThemeLayer, _ManifestModel]]:
        root = BUILTIN_THEMES / name
        if not (root / "theme.yaml").is_file():
            available = sorted(
                path.name for path in BUILTIN_THEMES.iterdir() if path.is_dir()
            )
            match = difflib.get_close_matches(name.casefold(), available, n=1)
            hint = f"; did you mean {match[0]}?" if match else ""
            raise ThemeError(
                [
                    f"theme: there is no built-in Theme named {name}{hint}"
                    f" (built-in: {', '.join(available)}; a local Theme is ./path)"
                ]
            )
        return self._layers(name, root, seen=seen)

    def _layers(
        self, name: str, root: Path, *, seen: tuple[str, ...]
    ) -> list[tuple[ThemeLayer, _ManifestModel]]:
        _reject_symlinks(name, root)
        manifest = _read_manifest(name, root)
        layers = [(ThemeLayer(name, root), manifest)]
        if manifest.extends is not None:
            if manifest.extends in (*seen, name):
                raise ThemeError([f"{name}: extends {manifest.extends} forms a cycle"])
            layers += self._builtin(manifest.extends, seen=(*seen, name))
        return layers


def _reject_symlinks(name: str, root: Path) -> None:
    for directory, dirnames, filenames in os.walk(root):
        for entry in (*dirnames, *filenames):
            path = Path(directory) / entry
            if path.is_symlink():
                raise ThemeError(
                    [
                        f"{name}: {path.relative_to(root)} is a symbolic link; "
                        "copy the file into the Theme instead"
                    ]
                )


def _read_manifest(name: str, root: Path) -> _ManifestModel:
    path = root / "theme.yaml"
    if not path.is_file():
        raise ThemeError([f"{name}: theme.yaml is missing"])
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=_StrictYAMLLoader)  # noqa: S506 - SafeLoader subclass
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" line {mark.line + 1}" if mark else ""
        raise ThemeError([f"{name}: theme.yaml{where} is not valid YAML"]) from None
    if not isinstance(data, dict):
        raise ThemeError([f"{name}: theme.yaml must be a mapping"])
    if "api_version" in data or data.get("api") != THEME_API:
        raise ThemeError(
            [
                f"{name}: theme.yaml must declare api: {THEME_API} "
                "(see docs/themes/authoring.md#migrating-from-api-2)"
            ]
        )
    try:
        manifest = _ManifestModel.model_validate(data)
    except ValidationError as exc:
        raise ThemeError(
            [
                f"{name}: theme.yaml {problem}"
                for problem in describe_validation_errors(exc.errors(), _ManifestModel)
            ]
        ) from None
    problems = _manifest_problems(manifest)
    if problems:
        raise ThemeError([f"{name}: theme.yaml {problem}" for problem in problems])
    return manifest


def _manifest_problems(manifest: _ManifestModel) -> list[str]:
    problems = []
    for option, spec in manifest.options.items():
        if not _OPTION_NAME.fullmatch(option):
            problems.append(f"options.{option}: use lowercase letters, digits, _")
        if spec.type == "choice" and not spec.values:
            problems.append(f"options.{option}: a choice needs values")
        try:
            _check_value(_spec(spec), spec.default)
        except ValueError as exc:
            problems.append(f"options.{option}.default: {exc}")
    for index, page in enumerate(manifest.pages):
        where = f"pages.{index}"
        placeholders = page.path.count("{slug}")
        if not _PAGE_PATH.fullmatch(page.path):
            problems.append(
                f"{where}.path: use lowercase segments ending with /, like /now/"
            )
        elif page.path in _COMPILER_PATHS or page.path.startswith(_COMPILER_PREFIXES):
            problems.append(f"{where}.path: {page.path} belongs to the compiler")
        if (placeholders == 1) != (page.for_each == "projects"):
            problems.append(
                f"{where}.path: use {{slug}} exactly once with for_each: projects, "
                "and not otherwise"
            )
        template = PurePosixPath(page.template)
        if (
            template.is_absolute()
            or ".." in template.parts
            or template.suffix != ".html"
            or ("{slug}" in page.template and page.for_each is None)
        ):
            problems.append(f"{where}.template: use a relative .html template name")
    for language, table in manifest.strings.items():
        for key in table:
            if not _STRING_KEY.fullmatch(key) or key in _RESERVED_STRING_KEYS:
                problems.append(
                    f"strings.{language}.{key}: use lowercase letters, digits, _ "
                    "(and not 'language')"
                )
    return problems


def _spec(model: _OptionModel) -> OptionSpec:
    return OptionSpec(
        model.type, model.default, tuple(model.values or ()), model.description
    )


def _check_value(spec: OptionSpec, value: object) -> object:
    kind = spec.type
    if kind in ("string", "color", "url", "choice") and not isinstance(value, str):
        raise ValueError("must be text")
    if kind == "boolean" and type(value) is not bool:
        raise ValueError("must be true or false")
    if kind == "integer" and type(value) is not int:
        raise ValueError("must be a whole number")
    if kind == "color" and value and not _COLOR.fullmatch(str(value)):
        raise ValueError("must be a hex color such as #a72f6a")
    if kind == "url" and value:
        validate_safe_href(str(value))
    if kind == "choice" and value not in spec.values:
        raise ValueError(f"must be one of {', '.join(spec.values)}")
    if kind == "list":
        if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
            raise ValueError("must be a list of text")
        return tuple(value)
    if kind == "posts":
        if not isinstance(value, list) or any(
            type(v) is not int or v <= 0 for v in value
        ):
            raise ValueError("must be a list of Blog Issue numbers")
        if len(set(value)) != len(value):
            raise ValueError("lists the same Issue twice")
        return tuple(value)
    return value


def _merge(name: str, layers: list[tuple[ThemeLayer, _ManifestModel]]) -> LoadedTheme:
    options: dict[str, OptionSpec] = {}
    pages: dict[str, PageSpec] = {}
    strings: dict[str, dict[str, str]] = {}
    for _, manifest in reversed(layers):  # parent first, the child overrides
        options.update({key: _spec(model) for key, model in manifest.options.items()})
        pages.update(
            {
                page.path: PageSpec(page.path, page.template, page.for_each)
                for page in manifest.pages
            }
        )
        for language, table in manifest.strings.items():
            strings.setdefault(language.casefold(), {}).update(table)
    static_reserved = [
        layer.name
        for layer, _ in layers
        if (layer.root / "static" / SHARED_ASSET_DIR).exists()
    ]
    if static_reserved:
        raise ThemeError(
            [
                f"{layer}: static/{SHARED_ASSET_DIR}/ is reserved for the compiler"
                for layer in static_reserved
            ]
        )
    return LoadedTheme(
        name=name,
        layers=tuple(layer for layer, _ in layers),
        options=options,
        pages=tuple(pages.values()),
        strings=strings,
    )
