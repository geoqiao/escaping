from __future__ import annotations

from dataclasses import dataclass
from importlib.abc import Traversable
from importlib.resources import files
from pathlib import Path, PurePosixPath

import yaml
from jinja2 import (
    BaseLoader,
    Environment,
    FileSystemLoader,
    PackageLoader,
    StrictUndefined,
)
from pydantic import BaseModel, ConfigDict, ValidationError

from .config import BuiltinThemeConfig, LocalThemeConfig

_THEME_API_VERSION = "1"
_REQUIRED_TEMPLATES = (
    "base.html",
    "home.html",
    "index.html",
    "post.html",
    "tag.html",
    "tags.html",
    "ideas.html",
    "idea.html",
    "about.html",
    "projects.html",
)


class ThemeResolutionError(RuntimeError):
    """Raised when a declared Theme cannot be loaded safely."""


class ThemeManifest(BaseModel):
    """Declarative Theme compatibility and resource contract."""

    model_config = ConfigDict(extra="forbid")

    api_version: str
    capabilities: list[str]
    required_templates: list[str]
    required_assets: list[str]


def _resource_at(root: Traversable, relative_path: str) -> Traversable:
    resource = root
    path = PurePosixPath(relative_path)
    parts = path.parts
    if (
        path.is_absolute()
        or "\\" in relative_path
        or not parts
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise ThemeResolutionError(f"unsafe theme resource path: {relative_path!r}")
    for part in parts:
        resource = resource.joinpath(part)
    return resource


def _copy_resource_tree(source: Traversable, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir():
            _copy_resource_tree(child, target)
        elif child.is_file():
            target.write_bytes(child.read_bytes())


@dataclass(frozen=True)
class LoadedTheme:
    """One validated Theme used for both templates and static assets."""

    name: str
    resource_root: Traversable
    template_loader: BaseLoader
    manifest: ThemeManifest

    @property
    def asset_url_path(self) -> str:
        return f"/templates/{self.name}"

    def read_text(self, relative_path: str) -> str:
        resource = _resource_at(self.resource_root, relative_path)
        if not resource.is_file():
            raise ThemeResolutionError(f"theme file is missing: {relative_path}")
        return resource.read_text(encoding="utf-8")

    def environment(self) -> Environment:
        return Environment(
            loader=self.template_loader,
            autoescape=True,
            undefined=StrictUndefined,
        )

    def copy_assets(self, output_dir: Path) -> None:
        static = _resource_at(self.resource_root, "static")
        if not static.is_dir():
            raise ThemeResolutionError("theme static asset directory is missing")
        destination = output_dir / "templates" / self.name / "static"
        _copy_resource_tree(static, destination)
        shared_comments = files("escaping").joinpath("static/comments.js")
        if not shared_comments.is_file():
            raise ThemeResolutionError("shared comments asset is missing")
        comments_target = destination / "js" / "comments.js"
        comments_target.parent.mkdir(parents=True, exist_ok=True)
        comments_target.write_bytes(shared_comments.read_bytes())


class ThemeLoader:
    """Load validated package or Config-relative Themes without network I/O."""

    def __init__(self, config_root: Path) -> None:
        if not config_root.is_absolute():
            raise ValueError("ThemeLoader config_root must be absolute")
        self.config_root = config_root

    def load(self, declaration: BuiltinThemeConfig | LocalThemeConfig) -> LoadedTheme:
        if isinstance(declaration, BuiltinThemeConfig):
            root = files("escaping").joinpath("themes").joinpath(declaration.name)
            if not root.is_dir():
                raise ThemeResolutionError(
                    f"built-in theme is missing: {declaration.name}"
                )
            template_loader: BaseLoader = PackageLoader(
                "escaping", f"themes/{declaration.name}"
            )
        else:
            root = self.config_root / declaration.path
            if not root.is_dir():
                raise ThemeResolutionError(f"local theme is missing: {root}")
            template_loader = FileSystemLoader(str(root))

        theme = LoadedTheme(
            name=declaration.name,
            resource_root=root,
            template_loader=template_loader,
            manifest=self._load_manifest(root),
        )
        self._validate(theme)
        return theme

    @staticmethod
    def _load_manifest(root: Traversable) -> ThemeManifest:
        manifest_path = root.joinpath("theme.yaml")
        if not manifest_path.is_file():
            raise ThemeResolutionError("theme manifest is missing: theme.yaml")
        try:
            data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            return ThemeManifest.model_validate(data)
        except (OSError, yaml.YAMLError, ValidationError) as exc:
            raise ThemeResolutionError(f"invalid theme manifest: {exc}") from exc

    @staticmethod
    def _validate(theme: LoadedTheme) -> None:
        if theme.manifest.api_version != _THEME_API_VERSION:
            raise ThemeResolutionError(
                f"theme api_version {theme.manifest.api_version!r} is not supported"
            )
        required_templates = dict.fromkeys(
            (*_REQUIRED_TEMPLATES, *theme.manifest.required_templates)
        )
        for filename in required_templates:
            if not _resource_at(theme.resource_root, filename).is_file():
                raise ThemeResolutionError(
                    f"theme manifest required template is missing: {filename}"
                )
        for relative_path in theme.manifest.required_assets:
            if not _resource_at(theme.resource_root, relative_path).is_dir():
                raise ThemeResolutionError(
                    "theme manifest required asset directory is missing: "
                    f"{relative_path}"
                )
