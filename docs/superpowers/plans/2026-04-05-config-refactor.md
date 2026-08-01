# Config-First Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `config.yaml` the primary source of truth, add missing validations, wire dead config fields into themes, and provide sensible defaults when optional config blocks are omitted.

**Architecture:** Keep the three-tier config model (Core / Personalization / Advanced) but fix three engineering gaps: (1) optional blocks (`about`, `navigation`) get sensible defaults instead of being required; (2) `advanced.language` is surfaced into templates and RSS; (3) env variables can override YAML values. CLI `repo` becomes optional, falling back to config.

**Tech Stack:** Python, Pydantic v2, Pydantic Settings, Jinja2, pytest.

---

## File Map

| File | Responsibility |
|------|----------------|
| `src/escaping/config.py` | Pydantic models, validation rules, multi-source merging (YAML + env + defaults). |
| `src/escaping/cli.py` | Make CLI `repo` argument optional; fallback to `config.yaml` value. |
| `src/escaping/services/render_service.py` | Expose `language` to templates and RSS feed; ensure all theme context is config-driven. |
| `templates/BearMinimal/base.html` | Use `{{ language }}` instead of hardcoded `zh-CN`. |
| `templates/PaperMint/base.html` | Use `{{ language }}`; replace hardcoded nav links with `navigation.items` loop. |
| `config.yaml` | Rename `GoogleSearchConsole` → `google_search_console` to match Python naming. |
| `tests/test_config.py` | Add tests for defaults, theme validator, and env-var override. |
| `tests/test_cli.py` | Update integration test to exercise optional `repo` behavior. |

---

## Task 1: Make `about` and `navigation` optional with sensible defaults

**Files:**
- Modify: `src/escaping/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test for empty-config defaults**

```python
def test_optional_blocks_provide_defaults():
    from escaping.config import AboutConfig, NavigationConfig, NavigationItem

    about = AboutConfig()
    assert about.bio == ""
    assert about.expertise == []
    assert about.links == []
    assert about.avatar == ""

    nav = NavigationConfig()
    assert len(nav.items) == 4
    assert nav.items[0] == NavigationItem(name="Blog", url="/blog/")
    assert nav.items[1] == NavigationItem(name="Tags", url="/tag/")
    assert nav.items[2] == NavigationItem(name="About", url="/about.html")
    assert nav.items[3] == NavigationItem(name="RSS", url="/atom.xml")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_optional_blocks_provide_defaults -v`
Expected: FAIL — `AboutConfig()` raises validation error for missing `bio` and `links`.

- [ ] **Step 3: Update models to provide defaults**

Edit `src/escaping/config.py`:

```python
class AboutConfig(BaseModel):
    """关于页面配置（可选）"""

    avatar: str = ""
    bio: str = ""
    expertise: list[str] = Field(default_factory=list)
    links: list[AboutLink] = Field(default_factory=list)
```

And update `NavigationConfig`:

```python
class NavigationConfig(BaseModel):
    """导航配置（可选，提供默认导航）"""

    items: list[NavigationItem] = Field(
        default_factory=lambda: [
            NavigationItem(name="Blog", url="/blog/"),
            NavigationItem(name="Tags", url="/tag/"),
            NavigationItem(name="About", url="/about.html"),
            NavigationItem(name="RSS", url="/atom.xml"),
        ]
    )
```

Then make `about` optional at the `Settings` level:

```python
class Settings(BaseSettings):
    blog: BlogConfig
    github: GithubConfig
    about: AboutConfig = Field(default_factory=AboutConfig)
    # ... rest unchanged
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_optional_blocks_provide_defaults -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/escaping/config.py tests/test_config.py
git commit -m "feat: make about and navigation optional with sensible defaults"
```

---

## Task 2: Add theme-existence validator

**Files:**
- Modify: `src/escaping/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test for theme validation**

```python
import pytest
from pydantic import ValidationError
from escaping.config import ThemeConfig


def test_theme_must_exist():
    with pytest.raises(ValidationError, match="not found in templates"):
        ThemeConfig(name="NonExistentTheme")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_theme_must_exist -v`
Expected: FAIL — `ValidationError` pattern not found (validation currently passes for bad theme names).

- [ ] **Step 3: Add validator to `ThemeConfig`**

Edit `src/escaping/config.py` (add `field_validator` import at the top):

```python
from pydantic import BaseModel, Field, HttpUrl, field_validator
```

And update `ThemeConfig`:

```python
class ThemeConfig(BaseModel):
    """主题配置（可选，默认 BearMinimal）"""

    name: str = "BearMinimal"

    @field_validator("name")
    @classmethod
    def _theme_dir_must_exist(cls, v: str) -> str:
        if not (Path("templates") / v).is_dir():
            raise ValueError(f"Theme '{v}' not found in templates/")
        return v

    @property
    def path(self) -> Path:
        """主题路径，如 'BearMinimal' → templates/BearMinimal"""
        return Path("templates") / self.name

    @property
    def seo(self) -> Path:
        """SEO 模板路径"""
        return Path("templates/seo")

    @property
    def url_path(self) -> str:
        """URL 路径，如 /templates/BearMinimal"""
        return f"/templates/{self.name}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_theme_must_exist -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/escaping/config.py tests/test_config.py
git commit -m "feat: validate that configured theme exists on disk"
```

---

## Task 3: Rename `GoogleSearchConsole` to `google_search_console` in code and YAML

**Files:**
- Modify: `src/escaping/config.py`
- Modify: `config.yaml`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test for the new key**

```python
def test_google_search_console_key_matches_python_name():
    from escaping.config import get_settings

    settings = get_settings()
    # Should be reachable via snake_case attribute regardless of YAML key
    assert hasattr(settings, "google_search_console")
```

- [ ] **Step 2: Run test to verify it fails (or just check current import)**

Run: `pytest tests/test_config.py::test_google_search_console_key_matches_python_name -v`
Expected: PASS (attribute already exists), but we will still rename the alias so YAML key and Python name are consistent.

- [ ] **Step 3: Remove alias and update YAML key**

Edit `src/escaping/config.py`:

```python
google_search_console: GoogleSearchConsoleConfig = Field(
    default_factory=GoogleSearchConsoleConfig,
)
```

Edit `config.yaml`, rename section:

```yaml
# ============================================
# SEO 配置（可选）
# ==========================================
google_search_console:
  content: DRggZlykSzc8M9TyaS0BPSRE7Kvw8W9hHt5pZrIMm3Y
  verify: true
```

- [ ] **Step 4: Run existing config tests**

Run: `pytest tests/test_config.py -v`
Expected: All PASS (tests read the real `config.yaml`, which now uses the new key).

- [ ] **Step 5: Commit**

```bash
git add src/escaping/config.py config.yaml tests/test_config.py
git commit -m "refactor: rename GoogleSearchConsole to google_search_console for consistency"
```

---

## Task 4: Support environment-variable overrides of YAML config

**Files:**
- Modify: `src/escaping/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test for env override**

```python
import os


def test_env_var_overrides_yaml():
    from escaping.config import Settings

    os.environ["APP_BLOG__TITLE"] = "Env Blog Title"
    try:
        settings = Settings()
        assert settings.blog.title == "Env Blog Title"
    finally:
        del os.environ["APP_BLOG__TITLE"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_env_var_overrides_yaml -v`
Expected: FAIL — current `model_validate(data)` bypasses env parsing, so title comes from YAML, not env.

- [ ] **Step 3: Implement custom YAML settings source**

Add import at the top of `src/escaping/config.py`:

```python
from pydantic_settings import PydanticBaseSettingsSource
```

Replace the `Settings` class `load_from_yaml` method and add a custom source so that priority is: init kwargs > env vars > YAML file > defaults.

Edit `src/escaping/config.py`:

```python
class YamlSettingsSource(PydanticBaseSettingsSource):
    """从 config.yaml 读取的低优先级配置源（可被 env 覆盖）"""

    def __init__(self, settings_cls, data: dict):
        self.data = data
        super().__init__(settings_cls)

    def __call__(self) -> dict[str, Any]:
        return self.data
```

Then update `Settings`:

```python
class Settings(BaseSettings):
    """应用配置。支持：CLI/代码参数 > 环境变量 > config.yaml > 默认值。"""

    blog: BlogConfig
    github: GithubConfig
    about: AboutConfig = Field(default_factory=AboutConfig)
    theme: ThemeConfig = Field(default_factory=ThemeConfig)
    navigation: NavigationConfig = Field(default_factory=NavigationConfig)
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)
    google_search_console: GoogleSearchConsoleConfig = Field(
        default_factory=GoogleSearchConsoleConfig,
    )

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_prefix="APP_",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        yaml_path = Path("config.yaml")
        yaml_data = {}
        if yaml_path.exists():
            with open(yaml_path, encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f) or {}
        yaml_settings = YamlSettingsSource(settings_cls, yaml_data)
        return (
            init_settings,
            env_settings,
            yaml_settings,
            dotenv_settings,
            file_secret_settings,
        )

    @classmethod
    def load_from_yaml(cls, yaml_path: Path) -> "Settings":
        """向后兼容：显式从 YAML 加载（内部仍走统一 source 逻辑）"""
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)
```

And update the global instance load:

```python
try:
    _settings = Settings()
except Exception as e:
    logger.debug(f"Config load skipped: {e}")
    _settings = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py::test_env_var_overrides_yaml -v`
Expected: PASS

- [ ] **Step 5: Run full config test suite**

Run: `pytest tests/test_config.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/escaping/config.py tests/test_config.py
git commit -m "feat: allow environment variables to override yaml config values"
```

---

## Task 5: Make CLI `repo` argument optional and config-first

**Files:**
- Modify: `src/escaping/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test for optional CLI repo**

```python
from unittest.mock import MagicMock, patch


@patch("escaping.cli.GitHubService")
@patch("escaping.cli.get_settings")
def test_blog_generator_uses_config_repo_when_cli_repo_missing(
    mock_get_settings, mock_gh_service_class
):
    mock_settings = MagicMock()
    mock_settings.github.repo = "configuser/configrepo"
    mock_get_settings.return_value = mock_settings

    mock_gh_service = mock_gh_service_class.return_value
    mock_repo = MagicMock()
    mock_gh_service.get_repo.return_value = mock_repo
    mock_gh_service.get_user_issues.return_value = []

    generator = BlogGenerator("fake-token")
    assert generator.repo_name == "configuser/configrepo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_blog_generator_uses_config_repo_when_cli_repo_missing -v`
Expected: FAIL — `BlogGenerator` currently requires two positional arguments.

- [ ] **Step 3: Update CLI and `BlogGenerator`**

Edit `src/escaping/cli.py`:

```python
def __init__(self, token: str, repo_name: str | None = None):
    self.gh = GitHubService(token)
    self.settings: Settings = get_settings()
    self.repo_name = repo_name or self.settings.github.repo
    self.render = RenderService()
```

And update the argument parser:

```python
def run_cli():
    import argparse

    parser = argparse.ArgumentParser(description="GitHub Blog Generator")
    parser.add_argument("token", help="GitHub Personal Access Token")
    parser.add_argument(
        "repo",
        nargs="?",
        default=None,
        help="GitHub Repository (e.g., user/repo). Defaults to github.repo in config.yaml.",
    )
    args = parser.parse_args()

    generator = BlogGenerator(args.token, args.repo)
    generator.generate()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py::test_blog_generator_uses_config_repo_when_cli_repo_missing -v`
Expected: PASS

- [ ] **Step 5: Run full CLI test suite**

Run: `pytest tests/test_cli.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/escaping/cli.py tests/test_cli.py
git commit -m "feat: make cli repo argument optional, defaulting to config.yaml"
```

---

## Task 6: Wire `advanced.language` into templates and RSS

**Files:**
- Modify: `src/escaping/services/render_service.py`
- Modify: `templates/BearMinimal/base.html`
- Modify: `templates/PaperMint/base.html`
- Test: `tests/test_renderer.py`

- [ ] **Step 1: Write the failing test for language in RSS and context**

```python
from unittest.mock import MagicMock, patch


@patch("escaping.services.render_service.get_settings")
def test_language_exposed_in_context_and_rss(mock_get_settings):
    mock_settings = MagicMock()
    mock_settings.blog.url = "https://example.com"
    mock_settings.blog.title = "T"
    mock_settings.blog.description = "D"
    mock_settings.blog.author = "A"
    mock_settings.github.name = "user"
    mock_settings.github.repo = "user/repo"
    mock_settings.theme.path = "templates/BearMinimal"
    mock_settings.theme.url_path = "/templates/BearMinimal"
    mock_settings.google_search_console.content = ""
    mock_settings.about.avatar = ""
    mock_settings.about.bio = ""
    mock_settings.about.expertise = []
    mock_settings.about.links = []
    mock_settings.navigation.items = []
    mock_settings.advanced.language = "zh-TW"
    mock_get_settings.return_value = mock_settings

    from escaping.services.render_service import RenderService

    rs = RenderService()
    ctx = rs._get_common_context()
    assert ctx["language"] == "zh-TW"

    # RSS should include language
    issue = MagicMock()
    issue.number = 1
    issue.title = "Post"
    issue.body = "Body"
    issue.created_at = None
    issue.updated_at = None
    rss = rs.generate_rss([issue], {"1": "1-post"})
    assert 'xml:lang="zh-TW"' in rss or "lang=\"zh-TW\"" in rss or "zh-TW" in rss
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_renderer.py::test_language_exposed_in_context_and_rss -v`
Expected: FAIL — `language` key not in context, and RSS does not set language.

- [ ] **Step 3: Expose `language` in render service and RSS**

Edit `src/escaping/services/render_service.py`:

In `_get_common_context`, add:

```python
"language": self.settings.advanced.language,
```

So the method becomes:

```python
def _get_common_context(self) -> dict[str, Any]:
    """获取所有模板共用的上下文变量。"""
    return {
        "blog_title": self.settings.blog.title,
        "github_name": self.settings.github.name,
        "github_repo": self.settings.github.repo,
        "blog_url": str(self.settings.blog.url),
        "rss_atom_path": "atom.xml",
        "author_name": self.settings.blog.author,
        "meta_description": self.settings.blog.description,
        "google_search_verification": self.settings.google_search_console.content,
        "theme_path": self.settings.theme.url_path,
        "navigation": self.settings.navigation,
        "about_avatar": self.settings.about.avatar,
        "about_bio": self.settings.about.bio,
        "about_expertise": self.settings.about.expertise,
        "about_links": self.settings.about.links,
        "language": self.settings.advanced.language,
    }
```

In `generate_rss`, after `fg.description(...)` add:

```python
fg.language(self.settings.advanced.language)
```

- [ ] **Step 4: Update templates to use `{{ language }}`**

Edit `templates/BearMinimal/base.html`, line 2:

```html
<html lang="{{ language }}">
```

Edit `templates/PaperMint/base.html`, line 2:

```html
<html lang="{{ language }}">
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_renderer.py::test_language_exposed_in_context_and_rss -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/escaping/services/render_service.py templates/BearMinimal/base.html templates/PaperMint/base.html tests/test_renderer.py
git commit -m "feat: wire advanced.language into templates and rss feed"
```

---

## Task 7: Make PaperMint navigation config-driven

**Files:**
- Modify: `templates/PaperMint/base.html`
- Test: `tests/test_template_integrity.py`

- [ ] **Step 1: Write the failing test for PaperMint nav config**

```python
from pathlib import Path


def test_papermint_nav_uses_config_variables():
    template_path = Path("templates/PaperMint/base.html")
    content = template_path.read_text(encoding="utf-8")
    # Should use Jinja2 loop instead of hardcoded /blog/, /tag, etc.
    assert "{% for item in navigation.items %}" in content
    assert "{{ item.url }}" in content
    assert "{{ item.name }}" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_template_integrity.py::test_papermint_nav_uses_config_variables -v`
Expected: FAIL — PaperMint currently has hardcoded `<li><a href="/blog/">...</a></li>` links.

- [ ] **Step 3: Replace hardcoded nav with config-driven loop**

Edit `templates/PaperMint/base.html`, replace the nav `<ul>` block (around lines 51-56):

```html
<ul class="nav-links">
    {% for item in navigation.items %}
    <li><a href="{{ item.url }}">{{ item.name }}</a></li>
    {% endfor %}
    <li><button class="theme-toggle" aria-label="Toggle theme">🌙</button></li>
</ul>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_template_integrity.py::test_papermint_nav_uses_config_variables -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add templates/PaperMint/base.html tests/test_template_integrity.py
git commit -m "fix: make PaperMint navigation use config-driven items"
```

---

## Self-Review

**Spec coverage check:**
- Config-file-first? Yes — Task 5 makes CLI `repo` optional, defaulting to YAML.
- Corresponding validations? Yes — Task 2 adds theme-existence validator.
- Theme code references config entirely? Yes — Task 6 wires `language`, Task 7 wires `navigation.items` into both templates.
- Empty-config defaults? Yes — Task 1 gives `about` and `navigation` sensible defaults.

**Placeholder scan:**
- No "TBD", "TODO", or vague "add validation" steps.
- Every code change is shown in full.
- Every test command is exact.

**Type consistency:**
- `BlogGenerator.__init__` signature changes to `repo_name: str | None = None`.
- `navigation.items` is always `list[NavigationItem]`.
- `language` is exposed as a string in Jinja2 context.

---

## Final Verification

After all tasks are complete, run the full test suite:

```bash
pytest -v
```

Expected: All tests pass.
