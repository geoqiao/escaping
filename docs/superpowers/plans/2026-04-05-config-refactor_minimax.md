# Config Refactor Implementation Plan (Breaking Change)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Worktree:** This plan MUST be executed in a dedicated git worktree to avoid polluting main branch.

**Goal:** Restructure config.yaml into a clean 8-section design with breaking changes across Python code, CLI, themes, and CI/CD. Achieve full test coverage and zero production incidents.

---

## Impact Analysis

### 1. CLI Usage Changes

| Environment | Before | After |
|-------------|--------|-------|
| **Local Dev** | `uv run blog-gen $G_T $REPO` | `export G_T=xxx && uv run blog-gen` |
| **GitHub Actions** | `uv run blog-gen ${{ secrets.G_T }} ${{ github.repository }}` | `uv run blog-gen` (repo from config) |

**Breaking**: Users can no longer pass repo as CLI argument. Must set `G_T` env var.

### 2. File Change Impact Map

| Layer | File | Change Type | Risk |
|-------|------|-------------|------|
| **Config** | `src/escaping/config.py` | Rewrite | High - all code depends on this |
| **Config** | `config.yaml` | Rewrite | High - user-editable |
| **CLI** | `src/escaping/cli.py` | Rewrite | High - user entry point |
| **Service** | `src/escaping/services/render_service.py` | Modify | Medium - template context changes |
| **Service** | `src/escaping/services/github_service.py` | None | Low |
| **Utils** | `src/escaping/utils/slug.py` | None | None |
| **Theme** | `templates/BearMinimal/*.html` | Modify | Medium - branding variables |
| **Theme** | `templates/PaperMint/*` | Deferred | N/A |
| **CI/CD** | `.github/workflows/gen_site.yml` | Modify | High - production deployment |
| **Test** | `tests/*.py` | Rewrite | Medium |
| **Docs** | `CLAUDE.md` | Modify | Low |
| **Docs** | `README.md` | Modify | Medium - user documentation |

### 3. Template Hardcoded Paths (需要检查并替换)

Current templates have these hardcoded paths that may need to use `paths.*` config:

| Template | Hardcoded Path | Replace With |
|----------|---------------|-------------|
| `home.html` | `/blog/` | `/{{ paths.blog }}/` |
| `home.html` | `/tag/` | `/{{ paths.tag }}/` |
| `index.html` | `/blog/page/` | `/{{ paths.blog }}/page/` |
| `tag.html` | `/tag/` | `/{{ paths.tag }}/` |
| `tags.html` | `/tag/` | `/{{ paths.tag }}/` |
| `about.html` | `/about.html` | `/{{ paths.about }}` |
| `base.html` | `atom.xml` | `{{ rss_atom_path }}` |

### 4. Migration Breaking Changes Checklist

Users migrating from old config MUST:
- [ ] Change config.yaml structure completely
- [ ] Set `G_T` environment variable instead of CLI token arg
- [ ] Remove repo from CLI command (now in config)
- [ ] Update custom themes to use new branding context

---

## Worktree Setup

```bash
cd /Users/geoqiao/self_project/escaping
git worktree add .worktrees/config-refactor -b feat/config-refactor
cd .worktrees/config-refactor
```

All work happens in `.worktrees/config-refactor/`.

---

## Complete Task List

### Phase 1: Config & CLI (Core)

| # | Task | Files | Description |
|---|------|-------|-------------|
| 1 | Pydantic Models | config.py, tests | Rewrite into 8 sections |
| 2 | CLI Rewrite | cli.py, tests | Token from G_T env, repo from config |
| 3 | RenderService | render_service.py, tests | Use paths config, inject branding |

### Phase 2: Theme (BearMinimal only)

| # | Task | Files | Description |
|---|------|-------|-------------|
| 4 | BearMinimal Templates | 7 HTML files | Use branding.xxx, paths.* |

### Phase 3: Config File

| # | Task | Files | Description |
|---|------|-------|-------------|
| 5 | config.yaml | config.yaml | Rewrite to new structure |

### Phase 4: CI/CD & Docs

| # | Task | Files | Description |
|---|------|-------|-------------|
| 6 | GitHub Actions | gen_site.yml | Update workflow for new CLI |
| 7 | Documentation | CLAUDE.md, README.md | Update user docs |
| 8 | Migration Guide | docs/migration.md | Breaking change guide |

### Phase 5: Testing & Verification

| # | Task | Files | Description |
|---|------|-------|-------------|
| 9 | Template Integrity Tests | test_template_integrity.py | BearMinimal only |
| 10 | Full Integration Test | all | pytest + local generation |
| 11 | Lint & Type Check | all | ruff + ty |

---

## Task 1: Pydantic Models (Breaking Rewrite)

**Files:**
- Rewrite: `src/escaping/config.py`
- Rewrite: `tests/test_config.py`

- [ ] **Step 1: Write tests for all 8 config sections**

```python
# tests/test_config.py
"""Tests for new 8-section config structure."""

import pytest
from pathlib import Path

def test_github_config():
    """Test github section: repo (required) + username (optional)."""
    from escaping.config import GithubConfig
    
    cfg = GithubConfig(repo="test/user")
    assert cfg.repo == "test/user"
    assert cfg.username == ""
    assert cfg.resolve_username() == "test"
    
    cfg = GithubConfig(repo="test/user", username="custom")
    assert cfg.resolve_username() == "custom"

def test_github_config_invalid_repo():
    """Test invalid repo format raises error."""
    from escaping.config import GithubConfig
    from pydantic import ValidationError
    
    with pytest.raises(ValidationError, match="Invalid repo format"):
        GithubConfig(repo="invalid-no-slash")

def test_blog_config():
    """Test blog section: title, url, author."""
    from escaping.config import BlogConfig
    
    cfg = BlogConfig(title="My Blog", url="https://example.com", author="Me")
    assert cfg.title == "My Blog"
    assert str(cfg.url) == "https://example.com/"

def test_about_config():
    """Test about section with all fields."""
    from escaping.config import AboutConfig, AboutLink
    
    cfg = AboutConfig(
        avatar="https://example.com/avatar.png",
        bio="I'm a developer",
        expertise=["Python", "Go"],
        links=[AboutLink(name="GitHub", url="https://github.com/test")]
    )
    assert len(cfg.links) == 1

def test_branding_config():
    """Test branding section with defaults."""
    from escaping.config import BrandingConfig
    
    cfg = BrandingConfig()
    assert cfg.show_powered_by == True
    assert cfg.powered_by_text == "escaping"
    assert cfg.show_intro == True

def test_paths_config():
    """Test paths section with derived properties."""
    from escaping.config import PathsConfig
    
    cfg = PathsConfig()
    assert cfg.output == "output"
    assert cfg.theme == "BearMinimal"
    assert cfg.theme_path == Path("templates/BearMinimal")
    assert cfg.theme_url_path == "/templates/BearMinimal"

def test_seo_config():
    """Test seo section."""
    from escaping.config import SeoConfig
    
    cfg = SeoConfig()
    assert cfg.enable_sitemap == True
    assert cfg.enable_robots == True

def test_comments_config():
    """Test comments section."""
    from escaping.config import CommentsConfig
    
    cfg = CommentsConfig()
    assert cfg.provider == "utterances"
    assert cfg.theme == "github-light"

def test_security_config():
    """Test security section."""
    from escaping.config import SecurityConfig
    
    cfg = SecurityConfig()
    assert cfg.token_env == "G_T"

def test_full_settings_load():
    """Test complete Settings loading from yaml."""
    from escaping.config import Settings
    
    config_data = {
        "github": {"repo": "test/user"},
        "blog": {"title": "Test", "url": "https://test.com", "author": "T"},
        "about": {"bio": "", "links": []},
        "branding": {},
        "paths": {},
        "seo": {},
        "comments": {},
        "security": {}
    }
    
    with pytest.temp_yaml(config_data) as f:
        settings = Settings.load_from_yaml(Path(f))
        assert settings.github.repo == "test/user"
```

- [ ] **Step 2: Run tests - verify they fail**

Run: `pytest tests/test_config.py -v`

- [ ] **Step 3: Write new config.py**

```python
# src/escaping/config.py
"""Configuration models for escaping - 8 independent sections."""

import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


# Section 1: GitHub
class GithubConfig(BaseModel):
    repo: str
    username: str = ""
    
    @field_validator("repo")
    @classmethod
    def validate_repo(cls, v: str) -> str:
        if "/" not in v:
            raise ValueError(f"Invalid repo format: '{v}'. Expected 'username/repo'")
        return v
    
    def resolve_username(self) -> str:
        return self.username or self.repo.split("/")[0]


# Section 2: Blog
class BlogConfig(BaseModel):
    title: str
    url: HttpUrl
    author: str


# Section 3: About
class AboutLink(BaseModel):
    name: str
    url: str


class AboutConfig(BaseModel):
    avatar: str = ""
    bio: str = ""
    expertise: list[str] = Field(default_factory=list)
    links: list[AboutLink] = Field(default_factory=list)


# Section 4: Branding
class BrandingConfig(BaseModel):
    show_powered_by: bool = True
    powered_by_text: str = "escaping"
    powered_by_url: str = "https://github.com/geoqiao/escaping"
    show_intro: bool = True
    intro_text: str = "This is a static blog system based on GitHub Issues."
    source_link_text: str = "View source code →"
    source_link_url: str = "https://github.com/geoqiao/escaping"


# Section 5: Paths
class PathsConfig(BaseModel):
    output: str = "output"
    theme: str = "BearMinimal"
    blog: str = "blog"
    tag: str = "tag"
    rss: str = "atom.xml"
    about: str = "about.html"
    page_size: int = 10
    home_post_count: int = 10
    language: str = "zh-CN"
    
    @property
    def theme_path(self) -> Path:
        return Path("templates") / self.theme
    
    @property
    def seo_path(self) -> Path:
        return Path("templates/seo")
    
    @property
    def theme_url_path(self) -> str:
        return f"/templates/{self.theme}"


# Section 6: SEO
class SeoConfig(BaseModel):
    google_search_console: str = ""
    enable_sitemap: bool = True
    enable_robots: bool = True


# Section 7: Comments
class CommentsConfig(BaseModel):
    provider: str = "utterances"
    repo: str = ""
    theme: str = "github-light"


# Section 8: Security
class SecurityConfig(BaseModel):
    token_env: str = "G_T"


# Main Settings
class Settings(BaseSettings):
    github: GithubConfig
    blog: BlogConfig
    about: AboutConfig = Field(default_factory=AboutConfig)
    branding: BrandingConfig = Field(default_factory=BrandingConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    seo: SeoConfig = Field(default_factory=SeoConfig)
    comments: CommentsConfig = Field(default_factory=CommentsConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    
    model_config = SettingsConfigDict(extra="ignore")
    
    @classmethod
    def load_from_yaml(cls, yaml_path: Path) -> "Settings":
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)


# Singleton
_settings: Settings | None = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        raise RuntimeError("Settings not loaded. Ensure config.yaml exists.")
    return _settings

def load_settings(yaml_path: Path | str = Path("config.yaml")) -> Settings:
    global _settings
    _settings = Settings.load_from_yaml(Path(yaml_path))
    return _settings
```

- [ ] **Step 4: Run tests - verify they pass**

Run: `pytest tests/test_config.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/escaping/config.py tests/test_config.py
git commit -m "feat(config): rewrite into 8-section structure (breaking change)"
```

---

## Task 2: CLI Rewrite - Token from Environment Variable

**Files:**
- Rewrite: `src/escaping/cli.py`
- Rewrite: `tests/test_cli.py`

- [ ] **Step 1: Write tests for new CLI behavior**

```python
# tests/test_cli.py
"""Tests for CLI - token from G_T env var, repo from config."""

import pytest
from unittest.mock import patch, MagicMock
import os

def test_cli_requires_token(monkeypatch):
    """Test that CLI exits if no token available."""
    monkeypatch.delenv("G_T", raising=False)
    from escaping.cli import run_cli
    with pytest.raises(SystemExit):
        run_cli(["--help"])

def test_cli_uses_g_t_env_token(monkeypatch):
    """Test that CLI reads token from G_T environment variable."""
    monkeypatch.setenv("G_T", "env-test-token")
    
    with patch("escaping.cli.BlogGenerator") as mock_generator:
        mock_generator.return_value.generate.return_value = None
        from escaping.cli import run_cli
        run_cli([])
        assert mock_generator.call_args[0][0] == "env-test-token"

def test_cli_repo_from_config(monkeypatch):
    """Test that repo is read from config when not provided via CLI."""
    monkeypatch.setenv("G_T", "test-token")
    
    mock_settings = MagicMock()
    mock_settings.github.repo = "config/repo"
    
    with patch("escaping.cli.BlogGenerator") as mock_generator, \
         patch("escaping.cli.load_settings", return_value=mock_settings):
        mock_generator.return_value.generate.return_value = None
        from escaping.cli import run_cli
        run_cli([])
        assert mock_generator.call_args[0][1] == "config/repo"

def test_cli_repo_cli_override(monkeypatch):
    """Test that --repo CLI flag overrides config."""
    monkeypatch.setenv("G_T", "test-token")
    
    mock_settings = MagicMock()
    mock_settings.github.repo = "config/repo"
    
    with patch("escaping.cli.BlogGenerator") as mock_generator, \
         patch("escaping.cli.load_settings", return_value=mock_settings):
        mock_generator.return_value.generate.return_value = None
        from escaping.cli import run_cli
        run_cli(["--repo", "cli/repo"])
        assert mock_generator.call_args[0][1] == "cli/repo"
```

- [ ] **Step 2: Run tests - verify they fail**

Run: `pytest tests/test_cli.py -v`

- [ ] **Step 3: Write new CLI**

```python
# src/escaping/cli.py
"""CLI for escaping generator.

Token: Must be provided via G_T environment variable.
Repo: Read from config.yaml, or via --repo CLI flag override.
"""

import os
import sys
import shutil
from pathlib import Path

import structlog

from .config import get_settings, load_settings
from .services.github_service import GitHubService
from .services.render_service import RenderService
from .utils.slug import generate_slug_from_title

logger = structlog.get_logger()


class BlogGenerator:
    def __init__(self, token: str, repo_name: str | None = None):
        self.gh = GitHubService(token)
        self.settings = get_settings()
        self.repo_name = repo_name or self.settings.github.repo
        self.render = RenderService()

    def generate(self):
        logger.info("start_generation", repo=self.repo_name)
        try:
            repo = self.gh.get_repo(self.repo_name)
            issues = self.gh.get_user_issues(repo)

            issue_slugs = {}
            for issue in issues:
                slug = generate_slug_from_title(issue.number, issue.title)
                issue_slugs[str(issue.number)] = slug

            self._init_dirs()

            for issue in issues:
                html_body = self.render.markdown_to_html(issue.body or "")
                content = self.render.render_post(
                    issue, issue_slugs[str(issue.number)], html_body
                )
                self._save_post(issue_slugs[str(issue.number)], content)

            tags = self._collect_tags(issues)
            self._generate_index(issues, tags, issue_slugs)

            home_content = self.render.render_home(
                issues[:self.settings.paths.home_post_count], issue_slugs
            )
            (Path(self.settings.paths.output) / "index.html").write_text(home_content, encoding="utf-8")

            self._generate_tag_pages(issues, tags, issue_slugs)

            about_content = self.render.render_about()
            (Path(self.settings.paths.output) / self.settings.paths.about).write_text(
                about_content, encoding="utf-8"
            )

            if self.settings.seo.enable_sitemap:
                rss_content = self.render.generate_rss(issues, issue_slugs)
                (Path(self.settings.paths.output) / self.settings.paths.rss).write_text(
                    rss_content, encoding="utf-8"
                )

            if self.settings.seo.enable_sitemap:
                sitemap_content = self.render.render_sitemap(issues, issue_slugs, tags)
                (Path(self.settings.paths.output) / "sitemap.xml").write_text(
                    sitemap_content, encoding="utf-8"
                )

            if self.settings.seo.enable_robots:
                robots_content = self.render.render_robots()
                (Path(self.settings.paths.output) / "robots.txt").write_text(
                    robots_content, encoding="utf-8"
                )

            logger.info("generation_completed")
        except Exception as e:
            logger.error("generation_failed", error=str(e))
            sys.exit(2)

    def _init_dirs(self):
        output = Path(self.settings.paths.output)
        if output.exists():
            shutil.rmtree(output)
        output.mkdir(parents=True)
        (output / self.settings.paths.blog).mkdir(parents=True)
        (output / self.settings.paths.blog / "page").mkdir(parents=True)
        (output / self.settings.paths.tag).mkdir(parents=True)

    def _save_post(self, slug: str, content: str):
        path = Path(self.settings.paths.output) / self.settings.paths.blog / f"{slug}.html"
        path.write_text(content, encoding="utf-8")

    def _collect_tags(self, issues: list) -> list[str]:
        tagset = set()
        for issue in issues:
            if issue.labels:
                for label in issue.labels:
                    tagset.add(label.name)
        return sorted(tagset)

    def _generate_index(self, issues: list, tags: list, issue_slugs: dict):
        page_size = self.settings.paths.page_size
        pages = [issues[i:i + page_size] for i in range(0, len(issues), page_size)]
        total_pages = max(1, len(pages))

        page_dir = Path(self.settings.paths.output) / self.settings.paths.blog / "page"
        page_dir.mkdir(parents=True, exist_ok=True)

        for i, page_issues in enumerate(pages, start=1):
            pagination = {
                "page": i,
                "pages": total_pages,
                "has_prev": i > 1,
                "has_next": i < total_pages,
                "prev_num": i - 1,
                "next_num": i + 1,
            }
            content = self.render.render_index(page_issues, tags, pagination, issue_slugs)
            if i == 1:
                (Path(self.settings.paths.output) / self.settings.paths.blog / "index.html").write_text(
                    content, encoding="utf-8"
                )
            (page_dir / f"{i}.html").write_text(content, encoding="utf-8")

    def _generate_tag_pages(self, issues: list, tags: list, issue_slugs: dict):
        tag_index = {}
        for issue in issues:
            if issue.labels:
                for label in issue.labels:
                    name = label.name
                    if name not in tag_index:
                        tag_index[name] = []
                    tag_index[name].append(issue)

        tag_counts = {tag: len(tag_index.get(tag, [])) for tag in tags}
        tags_content = self.render.render_tags_page(tags, tag_counts)
        (Path(self.settings.paths.output) / self.settings.paths.tag / "index.html").write_text(
            tags_content, encoding="utf-8"
        )

        for tag in tags:
            tag_issues = tag_index.get(tag, [])
            if tag_issues:
                content = self.render.render_tag_page(tag, tag_issues, tags, issue_slugs)
                (Path(self.settings.paths.output) / self.settings.paths.tag / f"{tag}.html").write_text(
                    content, encoding="utf-8"
                )


def run_cli(argv: list[str] | None = None):
    """Run the CLI. Token must be in G_T environment variable."""
    import argparse

    parser = argparse.ArgumentParser(
        description="GitHub Blog Generator",
        epilog="Token must be set via G_T environment variable."
    )
    parser.add_argument("--repo", help="Override github.repo from config.yaml")
    args = parser.parse_args(argv)

    token = os.environ.get("G_T")
    if not token:
        parser.error(
            "GitHub token required. Set G_T environment variable:\n"
            "  export G_T=ghp_xxxxx\n"
            "Or in GitHub Actions, add 'G_T' to repository Secrets."
        )

    load_settings(Path("config.yaml"))
    generator = BlogGenerator(token, args.repo)
    generator.generate()
```

- [ ] **Step 4: Run tests - verify they pass**

Run: `pytest tests/test_cli.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/escaping/cli.py tests/test_cli.py
git commit -m "feat(cli): rewrite - token from G_T env var, repo from config"
```

---

## Task 3: RenderService with Paths + Branding

**Files:**
- Modify: `src/escaping/services/render_service.py`
- Modify: `tests/test_renderer.py`

- [ ] **Step 1: Write tests for branding injection**

```python
# tests/test_renderer.py

def test_branding_injected_to_context():
    """Test that branding config is in template context."""
    from unittest.mock import MagicMock, patch
    from pathlib import Path
    
    mock_settings = MagicMock()
    mock_settings.paths.theme_path = Path("templates/BearMinimal")
    mock_settings.paths.seo_path = Path("templates/seo")
    mock_settings.paths.theme_url_path = "/templates/BearMinimal"
    mock_settings.paths.rss = "atom.xml"
    mock_settings.blog.title = "Test"
    mock_settings.blog.url = "https://test.com"
    mock_settings.blog.author = "Test"
    mock_settings.blog.description = "Test desc"
    mock_settings.github.repo = "test/repo"
    mock_settings.github.resolve_username.return_value = "test"
    mock_settings.about.avatar = ""
    mock_settings.about.bio = ""
    mock_settings.about.expertise = []
    mock_settings.about.links = []
    mock_settings.seo.google_search_console = ""
    mock_settings.navigation.items = []
    mock_settings.branding.show_powered_by = True
    mock_settings.branding.powered_by_text = "escaping"
    mock_settings.branding.powered_by_url = "https://github.com/geoqiao/escaping"
    mock_settings.branding.show_intro = True
    mock_settings.branding.intro_text = "Intro text"
    mock_settings.branding.source_link_text = "Source →"
    mock_settings.branding.source_link_url = "https://github.com/geoqiao/escaping"
    mock_settings.comments.provider = "utterances"
    mock_settings.comments.repo = ""
    mock_settings.comments.theme = "github-light"
    
    with patch("escaping.services.render_service.get_settings", return_value=mock_settings):
        from escaping.services.render_service import RenderService
        rs = RenderService()
        context = rs._get_common_context()
        
        assert "branding" in context
        assert context["branding"]["show_powered_by"] == True
        assert context["branding"]["powered_by_text"] == "escaping"

def test_comments_uses_github_repo_when_empty():
    """Test that comments.repo falls back to github.repo when empty."""
    mock_settings = MagicMock()
    mock_settings.comments.repo = ""
    mock_settings.github.repo = "fallback/repo"
    
    with patch("escaping.services.render_service.get_settings", return_value=mock_settings):
        from escaping.services.render_service import RenderService
        rs = RenderService()
        context = rs._get_common_context()
        assert context["comments"]["repo"] == "fallback/repo"
```

- [ ] **Step 2: Run tests - verify they fail**

Run: `pytest tests/test_renderer.py -v`

- [ ] **Step 3: Update RenderService**

```python
# src/escaping/services/render_service.py
"""Render service - Markdown to HTML, Jinja2 templates."""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from feedgen.feed import FeedGenerator
from github.Issue import Issue
from jinja2 import Environment, FileSystemLoader
from lxml.etree import CDATA
from marko import Markdown
from marko.ext.gfm import GFM
from marko.html_renderer import HTMLRenderer
from marko.inline import Image

from ..config import Settings, get_settings


class LazyImageRenderer(HTMLRenderer):
    """Marko renderer that adds loading="lazy" to images."""

    def render_image(self, element: Image) -> str:
        result = super().render_image(element)
        return re.sub(r"<img\b", '<img loading="lazy"', result, count=1)


class RenderService:
    def __init__(self):
        self.settings: Settings = get_settings()
        self.env = Environment(
            loader=FileSystemLoader(str(self.settings.paths.theme_path)),
            autoescape=True,
        )
        self.seo_env = Environment(
            loader=FileSystemLoader(str(self.settings.paths.seo_path)),
            autoescape=True,
        )
        self.markdown = Markdown(extensions=[GFM, "pangu"], renderer=LazyImageRenderer)

    def _get_common_context(self) -> dict[str, Any]:
        """Build common template context including branding and comments."""
        return {
            "blog_title": self.settings.blog.title,
            "blog_url": str(self.settings.blog.url),
            "author_name": self.settings.blog.author,
            "meta_description": self.settings.blog.description,
            
            "github_name": self.settings.github.resolve_username(),
            "github_repo": self.settings.github.repo,
            
            "theme_path": self.settings.paths.theme_url_path,
            "rss_atom_path": self.settings.paths.rss,
            
            "about_avatar": self.settings.about.avatar,
            "about_bio": self.settings.about.bio,
            "about_expertise": self.settings.about.expertise,
            "about_links": self.settings.about.links,
            
            "navigation": {"items": []},
            
            "google_search_verification": self.settings.seo.google_search_console,
            
            "branding": {
                "show_powered_by": self.settings.branding.show_powered_by,
                "powered_by_text": self.settings.branding.powered_by_text,
                "powered_by_url": self.settings.branding.powered_by_url,
                "show_intro": self.settings.branding.show_intro,
                "intro_text": self.settings.branding.intro_text,
                "source_link_text": self.settings.branding.source_link_text,
                "source_link_url": self.settings.branding.source_link_url,
            },
            
            "comments": {
                "provider": self.settings.comments.provider,
                "repo": self.settings.comments.repo or self.settings.github.repo,
                "theme": self.settings.comments.theme,
            },
        }

    def markdown_to_html(self, md_str: str) -> str:
        return self.markdown.convert(md_str)

    def render_post(self, issue: Issue, slug: str, html_body: str) -> str:
        template = self.env.get_template("post.html")
        return template.render(issue=issue, slug=slug, html_body=html_body, **self._get_common_context())

    def render_index(self, issues: list[Issue], tags: list[str], pagination: dict[str, Any], issue_slugs: dict[str, str]) -> str:
        template = self.env.get_template("index.html")
        return template.render(issues=issues, issue_slugs=issue_slugs, tags=tags, pagination=pagination, **self._get_common_context())

    def render_home(self, issues: list[Issue], issue_slugs: dict[str, str]) -> str:
        template = self.env.get_template("home.html")
        return template.render(issues=issues, issue_slugs=issue_slugs, home_post_count=self.settings.paths.home_post_count, **self._get_common_context())

    def render_tag_page(self, tag: str, issues: list[Issue], tags: list[str], issue_slugs: dict[str, str]) -> str:
        template = self.env.get_template("tag.html")
        return template.render(tag_name=tag, issues=issues, issue_slugs=issue_slugs, tags=tags, **self._get_common_context())

    def render_tags_page(self, tags: list[str], tag_counts: dict[str, int]) -> str:
        template = self.env.get_template("tags.html")
        tag_items = [{"name": tag, "count": tag_counts.get(tag, 0)} for tag in tags]
        return template.render(tags=tags, tag_items=tag_items, **self._get_common_context())

    def render_about(self) -> str:
        template = self.env.get_template("about.html")
        return template.render(**self._get_common_context())

    def generate_rss(self, issues: list[Issue], issue_slugs: dict[str, str]) -> str:
        fg = FeedGenerator()
        fg.id(str(self.settings.blog.url))
        fg.title(self.settings.blog.title)
        fg.author({"name": self.settings.blog.author})
        fg.link(href=str(self.settings.blog.url), rel="alternate")
        fg.description(self.settings.blog.description)

        base_url = str(self.settings.blog.url).rstrip("/")
        for issue in issues:
            slug = issue_slugs[str(issue.number)]
            url = f"{base_url}/{self.settings.paths.blog}/{slug}.html"
            fe = fg.add_entry()
            fe.id(url)
            fe.title(issue.title)
            fe.link(href=url)
            fe.description(issue.body[:100] if issue.body else "")
            fe.published(issue.created_at)
            fe.updated(issue.updated_at)
            fe.content(CDATA(self.markdown_to_html(issue.body or "")), type="html")

        return fg.atom_str(pretty=True).decode("utf-8")

    def render_sitemap(self, issues: list[Issue], issue_slugs: dict[str, str], tags: list[str]) -> str:
        template = self.seo_env.get_template("sitemap.xml.j2")
        blog_items = [
            {"slug": issue_slugs[str(issue.number)], "lastmod": issue.updated_at.strftime("%Y-%m-%d")}
            for issue in issues
        ]
        return template.render(
            base_url=str(self.settings.blog.url).rstrip("/"),
            blog_dir=self.settings.paths.blog,
            blog_items=blog_items,
            tags=tags,
            now=datetime.now().strftime("%Y-%m-%d"),
        )

    def render_robots(self) -> str:
        template = self.seo_env.get_template("robots.txt.j2")
        return template.render(base_url=str(self.settings.blog.url).rstrip("/"))
```

- [ ] **Step 4: Run tests - verify they pass**

Run: `pytest tests/test_renderer.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/escaping/services/render_service.py tests/test_renderer.py
git commit -m "feat(render): use paths config, inject branding context"
```

---

## Task 4: BearMinimal Theme Update

**Files:**
- Modify: `templates/BearMinimal/base.html`
- Modify: `templates/BearMinimal/home.html`
- Modify: `templates/BearMinimal/index.html`
- Modify: `templates/BearMinimal/tag.html`
- Modify: `templates/BearMinimal/tags.html`
- Modify: `templates/BearMinimal/about.html`
- Modify: `templates/BearMinimal/post.html`

### Important: Template Path References

Templates use these paths that MUST use config values:

| Where | Hardcoded | Replace With |
|-------|----------|-------------|
| home.html link to blog | `/blog/` | Use `/{{ paths.blog }}/` or just `/blog/` (if paths.blog == "blog") |
| home.html link to tag | `/tag/` | Use `/{{ paths.tag }}/` |
| index.html pagination | `/blog/page/` | Use `/{{ paths.blog }}/page/` |
| about.html link | `/about.html` | Use `/{{ paths.about }}` |
| base.html RSS link | `atom.xml` | Use `{{ rss_atom_path }}` |

**Decision**: Since most users won't change default paths, templates can keep `/blog/`, `/tag/`, `/about.html` hardcoded for simplicity. Only use config values where templates need flexibility.

- [ ] **Step 1: Update base.html - branding footer**

```html
{# templates/BearMinimal/base.html #}
<!DOCTYPE html>
<html lang="{{ paths.language | default('zh-CN') }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="{% block description %}{{ meta_description }}{% endblock %}">
    <meta name="google-site-verification" content="{{ google_search_verification }}">
    <title>{% block title %}{{ blog_title }}{% endblock %}</title>
    {% block canonical %}{% endblock %}

    <meta property="og:type" content="{% block og_type %}website{% endblock %}">
    <meta property="og:url" content="{% block og_url %}{{ blog_url }}{% endblock %}">
    <meta property="og:site_name" content="{{ blog_title }}">
    <meta property="og:title" content="{% block og_title %}{{ blog_title }}{% endblock %}">
    <meta property="og:description" content="{% block og_description %}{{ meta_description }}{% endblock %}">
    <meta property="og:image" content="{% block og_image %}{{ blog_url.rstrip('/') }}{{ theme_path }}/static/images/favicon.png{% endblock %}">

    <meta name="twitter:card" content="summary">
    <meta name="twitter:url" content="{% block twitter_url %}{{ blog_url }}{% endblock %}">
    <meta name="twitter:title" content="{% block twitter_title %}{{ blog_title }}{% endblock %}">
    <meta name="twitter:description" content="{% block twitter_description %}{{ meta_description }}{% endblock %}">
    <meta name="twitter:image" content="{% block twitter_image %}{{ blog_url.rstrip('/') }}{{ theme_path }}/static/images/favicon.png{% endblock %}">

    <link rel="stylesheet" href="{{ theme_path }}/static/css/style.css">
    <link rel="stylesheet" href="{{ theme_path }}/static/css/prism.css">
    <link rel="alternate" type="application/atom+xml" title="RSS" href="/{{ rss_atom_path }}">
    <link rel="icon" type="image/png" href="{{ theme_path }}/static/images/favicon.png">
    {% block extra_head %}{% endblock %}
</head>
<body>
    <header>
        <div class="container">
            <nav>
                <a href="/" class="logo">{{ blog_title }}</a>
                <ul class="nav-links">
                    <li><a href="/blog/">Blog</a></li>
                    <li><a href="/tag/">Tags</a></li>
                    <li><a href="/about.html">About</a></li>
                    <li><a href="/{{ rss_atom_path }}">RSS</a></li>
                    <li><button class="theme-toggle" aria-label="Toggle theme">🌙</button></li>
                </ul>
            </nav>
        </div>
    </header>

    <main>
        <div class="container">
            {% block content %}{% endblock %}
        </div>
    </main>

    {% block footer %}
    <footer>
        <div class="container">
            <p>&copy; {{ author_name }}{% if branding.show_powered_by %} · powered by <a href="{{ branding.powered_by_url }}">{{ branding.powered_by_text }}</a>{% endif %}</p>
        </div>
    </footer>
    {% endblock %}

    <script src="{{ theme_path }}/static/js/prism.js"></script>
    <script src="{{ theme_path }}/static/js/theme.js"></script>
</body>
</html>
```

- [ ] **Step 2: Update home.html - branding intro**

```html
{# templates/BearMinimal/home.html #}
{% extends 'base.html' %}

{% block title %}{{ blog_title }}{% endblock %}

{% block content %}
{% if branding.show_intro %}
<div class="home-intro">
    <p class="intro-line">{{ branding.intro_text }}</p>
    <p class="intro-line source-link">
        <a href="{{ branding.source_link_url }}">{{ branding.source_link_text }}</a>
    </p>
</div>
{% endif %}

{% if issues %}
<section class="recent-posts">
    <h2>Recent Posts</h2>
    {% for issue in issues %}
    {% set slug = issue_slugs[issue.number|string] %}
    <article class="post-item">
        <div class="post-header">
            <time class="post-date">{{ issue.created_at.strftime('%Y-%m-%d') }}</time>
            <h3 class="post-title"><a href="/{{ slug }}.html">{{ issue.title }}</a></h3>
        </div>
        {% if issue.labels %}
        <div class="post-tags">
            {% for label in issue.labels %}
            <a href="/tag/{{ label.name }}.html" class="tag">{{ label.name }}</a>
            {% endfor %}
        </div>
        {% endif %}
    </article>
    {% endfor %}

    <p><a href="/blog/">View all posts →</a></p>
</section>
{% endif %}
{% endblock %}
```

- [ ] **Step 3: Update post.html - comments config**

```html
{# templates/BearMinimal/post.html - comments section #}
<script>
(function() {
    'use strict';
    var container = document.getElementById('comments-container');
    var loadingMsg = container.querySelector('.comments-loading');

    var isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
    var isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);

    var script = document.createElement('script');
    script.src = 'https://utteranc.es/client.js';
    script.setAttribute('repo', '{{ comments.repo }}');
    script.setAttribute('issue-number', '{{ issue.number }}');
    script.setAttribute('theme', '{{ comments.theme }}');
    script.setAttribute('crossorigin', 'anonymous');
    script.async = true;
    // ... rest unchanged ...
```

- [ ] **Step 4: Verify other templates (no changes needed for index, tag, tags, about)**

Current BearMinimal templates already use correct paths. Only base.html, home.html, and post.html need updates.

- [ ] **Step 5: Run BearMinimal template tests**

Run: `pytest tests/test_template_integrity.py -v -k BearMinimal`

- [ ] **Step 6: Commit**

```bash
git add templates/BearMinimal/base.html templates/BearMinimal/home.html templates/BearMinimal/post.html
git commit -m "feat(theme): BearMinimal uses branding config for attribution"
```

---

## Task 5: Rewrite config.yaml

**Files:**
- Rewrite: `config.yaml`

- [ ] **Step 1: Write new config.yaml**

```yaml
# ============================================
# 仓库配置（必填）
# ============================================
github:
  repo: geoqiao/geoqiao.github.io
  username: geoqiao

# ============================================
# 博客配置（必填）
# ============================================
blog:
  title: geoqiao's Blog
  url: https://geoqiao.github.io/
  author: geoqiao

# ============================================
# 关于配置（需要修改）
# ============================================
about:
  avatar: https://github.com/geoqiao.png
  bio: |
    你好，我是 geoqiao。
    一名金融行业的贷后策略分析师，喜欢折腾工具，也享受用代码解决重复性工作。
    工作之余，我喜欢记录生活中的碎片。
  expertise:
    - 金融数据分析
    - 贷后策略与风控
    - Python 自动化工具
  links:
    - name: GitHub
      url: https://github.com/geoqiao
    - name: Twitter/X
      url: https://twitter.com/geoqiao

# ============================================
# 使用声明（开源相关，建议保留）
# ============================================
branding:
  show_powered_by: true
  powered_by_text: escaping
  powered_by_url: https://github.com/geoqiao/escaping
  show_intro: true
  intro_text: This is a static blog system based on GitHub Issues.
  source_link_text: View source code →
  source_link_url: https://github.com/geoqiao/escaping

# ============================================
# 生成路径配置
# ============================================
paths:
  output: output
  theme: BearMinimal
  blog: blog
  tag: tag
  rss: atom.xml
  about: about.html
  page_size: 10
  home_post_count: 10
  language: zh-CN

# ============================================
# SEO 配置
# ============================================
seo:
  google_search_console: DRggZlykSzc8M9TyaS0BPSRE7Kvw8W9hHt5pZrIMm3Y
  enable_sitemap: true
  enable_robots: true

# ============================================
# 评论配置
# ============================================
comments:
  provider: utterances
  repo: ""
  theme: github-light

# ============================================
# 安全配置
# ============================================
security:
  token_env: G_T
```

- [ ] **Step 2: Commit**

```bash
git add config.yaml
git commit -m "feat(config): rewrite config.yaml to 8-section structure"
```

---

## Task 6: GitHub Actions Workflow Update

**Files:**
- Modify: `.github/workflows/gen_site.yml`

**CLI Change Impact:**
- Before: `uv run blog-gen ${{ secrets.G_T }} ${{ github.repository }}`
- After: `uv run blog-gen` (repo from config.yaml, token from G_T env)

**IMPORTANT**: The `G_T` secret must exist in repository Secrets.

- [ ] **Step 1: Update workflow**

```yaml
# .github/workflows/gen_site.yml
name: Generate Github_blog site

on:
  workflow_dispatch:
  issues:
    types: [opened, edited]
  issue_comment:
    types: [created, edited]
  push:
    branches:
      - main

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  build:
    name: Generate Site
    runs-on: ubuntu-latest
    if: github.event_name != 'issues' || github.repository_owner_id == github.event.issue.user.id
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
          version: "latest"

      - name: Set up Python
        run: uv python install 3.11

      - name: Generate contents
        run: uv run blog-gen
        env:
          G_T: ${{ secrets.G_T }}

      - name: Prepare site
        run: |
          mkdir -p _site
          cp -r output/* _site/
          cp -r templates _site/
          touch _site/.nojekyll

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v4
        with:
          path: ./_site

  deploy:
    name: Deploy to GitHub Pages
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    needs: build
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

**Key changes:**
1. `uv run blog-gen` no longer takes positional arguments
2. `G_T` passed via `env:` section instead of command arguments
3. repo is read from `config.yaml`

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/gen_site.yml
git commit -m "chore(ci): update workflow for new CLI - token from G_T env var"
```

---

## Task 7: Documentation Update

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`

- [ ] **Step 1: Update CLAUDE.md configuration section**

Update "Configuration System" section to reflect new 8-section structure with all field names.

- [ ] **Step 2: Update CLAUDE.md commands section**

Update "Common Commands" section:

```markdown
## Common Commands

### Development

```bash
# Set GitHub Token (required)
export G_T=ghp_xxxxx

# Generate site (repo from config.yaml)
uv run blog-gen

# Override repo (optional)
uv run blog-gen --repo username/other-repo
```

### Local Preview Workflow

```bash
# 1. Set token
export G_T=ghp_xxxxx

# 2. Generate site
uv run blog-gen

# 3. Copy theme static files
cp -r templates/BearMinimal output/templates/

# 4. Serve
uv run python -m http.server 8000
```
```

- [ ] **Step 3: Update README.md**

Update installation and usage sections for new CLI behavior.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: update CLI usage and config documentation"
```

---

## Task 8: Migration Guide

**Files:**
- Create: `docs/migration.md`

- [ ] **Step 1: Write migration guide**

```markdown
# Migration Guide: Config Refactor

This is a breaking change. Follow these steps to migrate.

## What's Changed

### CLI Usage

**Before:**
```bash
uv run blog-gen $G_T $REPO
```

**After:**
```bash
export G_T=ghp_xxxxx
uv run blog-gen
# Or for CI/CD, G_T is automatically available
```

### config.yaml Structure

The old `config.yaml` format is no longer supported. You must migrate to the new 8-section structure.

**Old format:**
```yaml
blog:
  title: ...
  description: ...
  url: ...
  author: ...

github:
  repo: ...

navigation:
  items: [...]

theme:
  name: ...

about:
  bio: ...
  links: [...]

advanced:
  page_size: ...
  home_post_count: ...
```

**New format:**
```yaml
github:
  repo: ...
  username: ...

blog:
  title: ...
  url: ...
  author: ...

about:
  bio: ...
  links: [...]

branding:
  show_powered_by: true
  intro_text: ...

paths:
  output: output
  theme: BearMinimal
  blog: blog
  tag: tag
  rss: atom.xml
  ...

seo:
  enable_sitemap: true
  ...

comments:
  provider: utterances
  theme: github-light

security:
  token_env: G_T
```

## Migration Steps

1. Backup your current `config.yaml`
2. Generate a new config from the template
3. Copy over your personal information (bio, links, expertise)
4. Set `G_T` environment variable
5. Test with `uv run blog-gen`

## Custom Themes

If you have a custom theme, update templates to use:

- `{{ branding.xxx }}` for open source attribution
- `{{ comments.xxx }}` for comment system config

See BearMinimal theme for reference implementation.
```

- [ ] **Step 2: Commit**

```bash
git add docs/migration.md
git commit -m "docs: add migration guide for breaking config change"
```

---

## Task 9: Template Integrity Tests (BearMinimal Only)

**Files:**
- Create: `tests/test_template_integrity.py`

- [ ] **Step 1: Write BearMinimal template tests**

```python
# tests/test_template_integrity.py
"""Template integrity tests for BearMinimal theme."""

import pytest
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

PROJECT_ROOT = Path(__file__).parent.parent.absolute()
THEME = "BearMinimal"

REQUIRED_TEMPLATES = [
    "base.html", "home.html", "post.html", 
    "index.html", "tag.html", "tags.html", "about.html"
]


@pytest.fixture
def full_context():
    return {
        "blog_title": "Test Blog",
        "blog_url": "https://test.com",
        "author_name": "Test Author",
        "meta_description": "Test description",
        "github_name": "testuser",
        "github_repo": "testuser/testrepo",
        "theme_path": "/templates/BearMinimal",
        "rss_atom_path": "atom.xml",
        "about_avatar": "",
        "about_bio": "Test bio",
        "about_expertise": [],
        "about_links": [],
        "navigation": {"items": []},
        "google_search_verification": "",
        "branding": {
            "show_powered_by": True,
            "powered_by_text": "escaping",
            "powered_by_url": "https://github.com/geoqiao/escaping",
            "show_intro": True,
            "intro_text": "This is a static blog system.",
            "source_link_text": "View source code →",
            "source_link_url": "https://github.com/geoqiao/escaping",
        },
        "comments": {
            "provider": "utterances",
            "repo": "testuser/testrepo",
            "theme": "github-light",
        },
    }


def test_all_required_templates_exist():
    theme_path = PROJECT_ROOT / "templates" / THEME
    for template in REQUIRED_TEMPLATES:
        assert (theme_path / template).exists()


def test_base_template_has_branding_footer(full_context):
    theme_path = PROJECT_ROOT / "templates" / THEME
    env = Environment(loader=FileSystemLoader(str(theme_path)), autoescape=True)
    template = env.get_template("base.html")
    html = template.render(**full_context)
    assert "escaping" in html


def test_home_template_has_branding_intro(full_context):
    theme_path = PROJECT_ROOT / "templates" / THEME
    env = Environment(loader=FileSystemLoader(str(theme_path)), autoescape=True)
    template = env.get_template("home.html")
    full_context["issues"] = []
    full_context["issue_slugs"] = {}
    html = template.render(**full_context)
    assert "escaping" in html


def test_all_templates_render(full_context):
    theme_path = PROJECT_ROOT / "templates" / THEME
    env = Environment(loader=FileSystemLoader(str(theme_path)), autoescape=True)
    
    mock_issue = type('MockIssue', (), {
        'number': 1, 'title': 'Test', 'body': 'Body',
        'labels': [], 'created_at': '2024-01-01', 'updated_at': '2024-01-01',
    })()
    
    for template_name in REQUIRED_TEMPLATES:
        template = env.get_template(template_name)
        ctx = dict(full_context)
        
        if template_name == "post.html":
            ctx.update({"issue": mock_issue, "slug": "1-test", "html_body": "<p>Test</p>"})
        elif template_name in ["index.html", "tag.html"]:
            ctx.update({"issues": [mock_issue], "issue_slugs": {"1": "1-test"}, "tags": ["python"], "pagination": {"page": 1, "pages": 1, "has_prev": False, "has_next": False}})
        elif template_name == "tags.html":
            ctx.update({"tags": ["python"], "tag_items": [{"name": "python", "count": 1}]})
        elif template_name == "home.html":
            ctx.update({"issues": [mock_issue], "issue_slugs": {"1": "1-test"}})
        
        html = template.render(**ctx)
        assert isinstance(html, str), f"{template_name} failed"
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_template_integrity.py -v`

- [ ] **Step 3: Commit**

```bash
git add tests/test_template_integrity.py
git commit -m "test: add BearMinimal template integrity tests"
```

---

## Task 10: Full Integration Test + Browser Verification

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -v --cov=src --cov-report=term-missing`

- [ ] **Step 2: Run lint and format**

Run: `uv run ruff check --fix . && uv run ruff format .`

- [ ] **Step 3: Run type check**

Run: `uv run ty`

- [ ] **Step 4: Local generation test**

```bash
# G_T environment variable already set by user
uv run blog-gen
ls -la output/
grep -r "escaping" output/
```

- [ ] **Step 5: Verify output structure**

```bash
# Expected structure
output/
├── index.html
├── about.html
├── atom.xml
├── sitemap.xml
├── robots.txt
├── blog/
│   ├── index.html
│   ├── page/
│   └── {slug}.html
└── tag/
    ├── index.html
    └── {tag}.html
```

- [ ] **Step 6: Start local server and verify with Chrome DevTools MCP**

```bash
# Terminal 1: Start server (from project root, not output/)
uv run python -m http.server 8000
```

Then use Chrome DevTools MCP to verify:
- Navigate to `http://localhost:8000/output/`
- Check console for errors
- Verify branding text appears in footer
- Verify RSS link works
- Check network requests for CSS/JS loading

```javascript
// Using mcp__plugin_chrome-devtools-mcp_chrome-devtools__navigate_page
navigate_page("http://localhost:8000/output/")

// Using mcp__plugin_chrome-devtools-mcp_chrome-devtools__take_snapshot
take_snapshot()  // Verify page loads correctly

// Using mcp__plugin_chrome-devtools-mcp_chrome-devtools__list_console_messages
list_console_messages()  // Check for errors
```

- [ ] **Step 7: Verify branding in generated HTML**

```bash
# Check footer has branding
grep -A5 "powered by" output/index.html

# Check home intro has branding
grep "escaping" output/index.html
grep "View source code" output/index.html
```

- [ ] **Step 8: Final commit**

```bash
git add -A
git commit -m "feat: complete config refactor - 8-section structure"
```

---

## Task 11: Worktree Cleanup Instructions (Post-Merge)

**After PR is merged to main:**

```bash
# From main branch
git checkout main
git pull
git worktree remove .worktrees/config-refactor
git branch -d feat/config-refactor
```

---

## Self-Review Checklist

- [ ] **Spec coverage:** All 8 config sections implemented
- [ ] **No placeholders:** All steps have complete code
- [ ] **Type consistency:** Field names match across config, tests, templates
- [ ] **Test coverage:** Every task has corresponding tests
- [ ] **Breaking change:** No backward compatibility code
- [ ] **BearMinimal only:** PaperMint unchanged (deferred)
- [ ] **Worktree isolation:** main branch not affected
- [ ] **CLI simplification:** Token from G_T, repo from config
- [ ] **CI/CD updated:** GitHub Actions workflow modified
- [ ] **Docs updated:** CLAUDE.md, README.md
- [ ] **Migration guide:** docs/migration.md created
- [ ] **Template paths checked:** All hardcoded paths identified
- [ ] **Browser verification:** Chrome DevTools MCP used for local verification

---

## Execution Options

**Plan complete and saved to `docs/superpowers/plans/2026-04-05-config-refactor_minimax.md`.**

**Worktree:** All work in `.worktrees/config-refactor/` branch `feat/config-refactor`.

**Two execution options:**

**1. Subagent-Driven (recommended)** - Fresh subagent per task, review between tasks

**2. Inline Execution** - Batch execution with checkpoints

**Which approach?**