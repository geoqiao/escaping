"""Theme API 4: load a Theme directory, its parent, options and strings.

A Theme is templates, static files and ``theme.yaml``. A Theme on GitHub is
unpacked by a ``fetch`` function first (see remote_theme); loading itself never
touches the network. Templates run in Jinja's sandbox. See
docs/themes/authoring.md.
"""

from __future__ import annotations

import difflib
import os
import re
import shutil
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from functools import partial
from pathlib import Path
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
    TemplateRuntimeError,
    TemplateSyntaxError,
)
from jinja2.sandbox import SandboxedEnvironment
from pydantic import BaseModel, ConfigDict, StrictInt, ValidationError

from .config import (
    ConfigError,
    PagesConfig,
    describe_validation_errors,
    validate_safe_href,
)
from .remote_theme import PREFIX as REMOTE_PREFIX
from .remote_theme import DownloadError, RemoteTheme
from .routes import with_base
from .utils.frontmatter import _StrictYAMLLoader

THEME_API = 4
BUILTIN_THEMES = Path(__file__).parent / "themes"

#: Page kind -> templates tried in order; the first one the Theme has is used.
#: List pages fall back to ``blog.html``, single pages to ``post.html``.
TEMPLATE_CHAINS: dict[str, tuple[str, ...]] = {
    "home": ("home.html", "blog.html"),
    "blog": ("blog.html",),
    "ideas": ("ideas.html", "blog.html"),
    "tag": ("tag.html", "blog.html"),
    "post": ("post.html",),
    "idea": ("idea.html", "post.html"),
    "about": ("about.html", "post.html"),
    "tags": ("tags.html",),
    "projects": ("projects.html",),
}
#: Every Theme (or its parent) has these.
REQUIRED_TEMPLATES = ("blog.html", "post.html")
#: Pages with no fallback: the Theme needs the template while the page is on.
_OWN_TEMPLATE_PAGES = ("tags", "projects")
#: Rendered to ``404.html`` when present.
NOT_FOUND_TEMPLATE = "404.html"
#: Static files under this directory name are published by the compiler.
SHARED_ASSET_DIR = "escaping"

_OPTION_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_STRING_KEY = re.compile(r"^[a-z][a-z0-9_]*$")
_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_RESERVED_STRING_KEYS = frozenset({"language"})

#: Unpacks a Theme from GitHub and returns its directory.
Fetch = Callable[[RemoteTheme], Path]

OptionType = Literal[
    "string", "boolean", "integer", "color", "url", "choice", "list", "posts"
]


class ThemeError(ConfigError):
    """A Theme cannot be loaded, or the site's options do not fit it."""


class OptionSpec(BaseModel):
    """One option in theme.yaml."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: OptionType
    default: Any
    values: tuple[str, ...] = ()
    description: str = ""


class _ManifestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api: StrictInt
    extends: str | None = None
    options: dict[str, OptionSpec] = {}
    strings: dict[str, dict[str, str]] = {}


@dataclass(frozen=True)
class ThemeLayer:
    name: str
    root: Path
    #: Parent templates are reachable as ``@short_name/file.html``.
    short_name: str = ""


@dataclass(frozen=True)
class LoadedTheme:
    """A Theme merged with its parent: most specific layer first."""

    name: str
    layers: tuple[ThemeLayer, ...]
    options: Mapping[str, OptionSpec]
    strings: Mapping[str, Mapping[str, str]]

    @property
    def local_roots(self) -> tuple[Path, ...]:
        return tuple(
            layer.root
            for layer in self.layers
            if not layer.root.is_relative_to(BUILTIN_THEMES)
        )

    def environment(self, base: str = "") -> Environment:
        """The Jinja environment; ``base`` is the site's path for ``url``."""
        loaders: list[BaseLoader] = [
            FileSystemLoader(str(layer.root)) for layer in self.layers
        ]
        loaders.extend(
            PrefixLoader({f"@{layer.short_name}": FileSystemLoader(str(layer.root))})
            for layer in self.layers[1:]
        )
        # The sandbox keeps a template away from Python internals, files and
        # environment variables such as the token.
        environment = SandboxedEnvironment(
            loader=ChoiceLoader(loaders),
            autoescape=True,
            undefined=StrictUndefined,
            finalize=_printable,
        )
        environment.filters["url"] = partial(_url, base)
        return environment

    def has_template(self, name: str) -> bool:
        return any((layer.root / name).is_file() for layer in self.layers)

    def template_for(self, kind: str) -> str:
        """The template that renders ``kind``, following ``TEMPLATE_CHAINS``."""
        chain = TEMPLATE_CHAINS[kind]
        return next((name for name in chain if self.has_template(name)), chain[-1])

    def check(
        self, pages: PagesConfig | None = None, project_slugs: Iterable[str] = ()
    ) -> None:
        """Fail before any network access if a template is missing or invalid."""
        pages = pages or PagesConfig()
        problems = [
            f"{self.name}: missing template {name} (every Theme needs "
            f"{' and '.join(REQUIRED_TEMPLATES)})"
            for name in REQUIRED_TEMPLATES
            if not self.has_template(name)
        ]
        for kind in _OWN_TEMPLATE_PAGES:
            path = getattr(pages, kind)
            if path and not self.has_template(f"{kind}.html"):
                problems.append(
                    f"{self.name}: has no {kind}.html for the {kind} page {path}; "
                    f"add {kind}.html to the Theme, or set pages.{kind}: false "
                    "in config.yaml"
                )
        slugs = tuple(project_slugs)
        for page in pages.extra:
            for slug in slugs if page.for_each else (None,):
                template = page.template_for(slug)
                if not self.has_template(template):
                    problems.append(
                        f"pages.extra: {page.path_for(slug)} needs template "
                        f"{template}, which {self.name} does not have"
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


def _printable(value: object) -> object:
    """Fail on ``{{ none }}`` rather than writing the word None into a page."""
    if value is None:
        raise TemplateRuntimeError(
            "this value is none, so it cannot be printed; check it first with "
            "{% if … %} (tag.path, for example, is none when the tags pages are off)"
        )
    return value


def _url(base: str, value: str) -> str:
    """The ``url`` filter: ``'/assets/site.css'|url`` under the site's path.

    Route paths already include it, so an address that starts with the site's
    path is returned as is; so are full URLs and fragments.
    """
    if not isinstance(value, str):
        raise TypeError(f"url expects an address string, not {type(value).__name__}")
    if base and (value == base or value.startswith(f"{base}/")):
        return value
    return with_base(base, value)


def _is_template(name: str) -> bool:
    # ``@parent/...`` names repeat the parent's own files; built-ins are tested.
    return (
        name.endswith(".html")
        and not name.startswith("@")
        and name.split("/", 1)[0] != "static"
    )


class ThemeLoader:
    """Load a built-in, Config-relative or GitHub Theme."""

    def __init__(self, config_root: Path, fetch: Fetch | None = None) -> None:
        if not config_root.is_absolute():
            raise ValueError("ThemeLoader config_root must be absolute")
        self.config_root = config_root
        self.fetch = fetch

    def load(self, use: str) -> LoadedTheme:
        if use.startswith(REMOTE_PREFIX):
            layers = self._remote(use, seen=())
            name = use
        elif "/" in use:
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
            layers = self._layers(use, root.resolve(), root.name, seen=())
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
                    f" (built-in: {', '.join(available)}; a local Theme is ./path,"
                    " a Theme on GitHub is github.com/OWNER/REPOSITORY/FOLDER@VERSION)"
                ]
            )
        return self._layers(name, root, name, seen=seen)

    def _remote(
        self, name: str, *, seen: tuple[str, ...]
    ) -> list[tuple[ThemeLayer, _ManifestModel]]:
        try:
            theme = RemoteTheme.parse(name)
        except ValueError as exc:
            raise ThemeError([f"{name}: {exc}"]) from None
        if self.fetch is None:
            raise ValueError("ThemeLoader needs fetch to load a Theme from GitHub")
        try:
            root = self.fetch(theme)
        except DownloadError as exc:
            raise ThemeError([f"{name}: {exc}"]) from None
        return self._layers(name, root, theme.short_name, seen=seen)

    def _layers(
        self, name: str, root: Path, short_name: str, *, seen: tuple[str, ...]
    ) -> list[tuple[ThemeLayer, _ManifestModel]]:
        _reject_symlinks(name, root)
        manifest = _read_manifest(name, root)
        layers = [(ThemeLayer(name, root, short_name), manifest)]
        if (parent := manifest.extends) is not None:
            if parent in (*seen, name):
                raise ThemeError([f"{name}: extends {parent} forms a cycle"])
            if parent.startswith(REMOTE_PREFIX):
                layers += self._remote(parent, seen=(*seen, name))
            else:
                layers += self._builtin(parent, seen=(*seen, name))
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
    if data.get("api") != THEME_API:
        raise ThemeError(
            [
                f"{name}: theme.yaml must declare api: {THEME_API} "
                "(see docs/themes/authoring.md)"
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
            _check_value(spec, spec.default)
        except ValueError as exc:
            problems.append(f"options.{option}.default: {exc}")
    for language, table in manifest.strings.items():
        for key in table:
            if not _STRING_KEY.fullmatch(key) or key in _RESERVED_STRING_KEYS:
                problems.append(
                    f"strings.{language}.{key}: use lowercase letters, digits, _ "
                    "(and not 'language')"
                )
    return problems


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
    strings: dict[str, dict[str, str]] = {}
    for _, manifest in reversed(layers):  # parent first, the child overrides
        options.update(manifest.options)
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
        strings=strings,
    )
