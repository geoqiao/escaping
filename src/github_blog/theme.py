from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml
from jinja2 import ChoiceLoader, Environment, FileSystemLoader, StrictUndefined
from pydantic import BaseModel, ConfigDict, ValidationError

from .config import ThemeLockConfig

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
    """Raised when a locked declarative theme cannot be resolved safely."""


class ThemeManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_version: str
    capabilities: list[str]
    required_templates: list[str]
    required_assets: list[str]


@dataclass(frozen=True)
class ResolvedTheme:
    lock: ThemeLockConfig
    locked_dir: Path
    template_dirs: tuple[Path, ...]
    asset_dirs: tuple[Path, ...]

    def read_text(self, relative_path: str) -> str:
        for directory in self.template_dirs:
            path = directory / relative_path
            if path.is_file():
                return path.read_text(encoding="utf-8")
        raise ThemeResolutionError(f"theme file is missing: {relative_path}")

    def environment(self) -> Environment:
        return Environment(
            loader=ChoiceLoader(
                [FileSystemLoader(str(directory)) for directory in self.template_dirs]
            ),
            autoescape=True,
            undefined=StrictUndefined,
        )


class ThemeResolver:
    """Resolve one immutable theme commit with site overrides before the lock."""

    def __init__(
        self,
        root: Path,
        lock: ThemeLockConfig,
        *,
        theme_name: str = "geoqiao.me",
        override_dir: Path | None = None,
        fetch: Callable[[ThemeLockConfig, Path], None] | None = None,
    ) -> None:
        self.root = root
        self.lock = lock
        self.theme_name = theme_name
        self.override_dir = override_dir
        self.fetch = fetch

    @property
    def cache_dir(self) -> Path:
        return self.root / "cache"

    def resolve(self) -> ResolvedTheme:
        locked_dir = self._resolve_locked_dir()
        manifest = self._load_manifest(locked_dir)
        if manifest.api_version != self.lock.api_version:
            raise ThemeResolutionError(
                f"theme api_version {manifest.api_version!r} does not match lock {self.lock.api_version!r}"
            )
        self._validate_manifest(locked_dir, manifest)
        template_dirs = (
            (self.override_dir, locked_dir) if self.override_dir else (locked_dir,)
        )
        asset_dirs = tuple(
            directory for directory in template_dirs if (directory / "static").is_dir()
        )
        return ResolvedTheme(self.lock, locked_dir, template_dirs, asset_dirs)

    def update(
        self,
        lock: ThemeLockConfig | None = None,
        fetch: Callable[[ThemeLockConfig, Path], None] | None = None,
    ) -> ResolvedTheme:
        if lock is None or fetch is None:
            raise ThemeResolutionError(
                "theme updates require an explicit lock and fetch operation"
            )
        resolver = ThemeResolver(
            self.root,
            lock,
            theme_name=self.theme_name,
            override_dir=self.override_dir,
            fetch=fetch,
        )
        source = resolver.resolve()
        self.lock = lock
        self.fetch = fetch
        return source

    def _resolve_locked_dir(self) -> Path:
        cache_path = self.cache_dir / self.lock.commit / self.theme_name
        if cache_path.is_dir():
            return cache_path

        vendored_path = self.root / "templates" / self.theme_name
        if vendored_path.is_dir():
            return vendored_path

        if self.fetch is None:
            raise ThemeResolutionError(
                f"locked theme {self.lock.commit} is not cached; an exact fetch is required"
            )

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.fetch(self.lock, cache_path.parent)
        if not cache_path.is_dir():
            raise ThemeResolutionError(
                "exact theme fetch did not produce the locked theme directory"
            )
        return cache_path

    @staticmethod
    def _load_manifest(theme_dir: Path) -> ThemeManifest:
        manifest_path = theme_dir / "theme.yaml"
        if not manifest_path.is_file():
            raise ThemeResolutionError(f"theme manifest is missing: {manifest_path}")
        try:
            data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            return ThemeManifest.model_validate(data)
        except (OSError, yaml.YAMLError, ValidationError) as exc:
            raise ThemeResolutionError(f"invalid theme manifest: {exc}") from exc

    @staticmethod
    def _validate_manifest(theme_dir: Path, manifest: ThemeManifest) -> None:
        missing_templates = [
            filename
            for filename in (*_REQUIRED_TEMPLATES, *manifest.required_templates)
            if not (theme_dir / filename).is_file()
        ]
        if missing_templates:
            raise ThemeResolutionError(
                f"theme manifest required template is missing: {missing_templates[0]}"
            )
        missing_assets = [
            asset
            for asset in manifest.required_assets
            if not (theme_dir / asset).is_dir()
        ]
        if missing_assets:
            raise ThemeResolutionError(
                f"theme manifest required asset directory is missing: {missing_assets[0]}"
            )

    def copy_assets(self, destination: Path, source: ResolvedTheme) -> None:
        """Merge static assets with override files winning over locked files."""
        destination.mkdir(parents=True, exist_ok=True)
        for directory in reversed(source.asset_dirs):
            static = directory / "static"
            if static.is_dir():
                shutil.copytree(static, destination, dirs_exist_ok=True)
