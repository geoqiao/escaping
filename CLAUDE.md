# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`github-blog` is a Python-based static blog generator that uses GitHub Issues as a CMS. It fetches issues via GitHub API, renders them to HTML using Jinja2 templates, and generates SEO-friendly outputs (sitemap, RSS, robots.txt).

**Live Demo:** https://geoqiao.github.io/

## Architecture

### Dual-Repository Architecture

| Repository | Role | Contents |
|-----------|------|----------|
| `escaping` | Code repository | Source code, workflows (gen_site.yml, trigger.yml), templates |
| `geoqiao.github.io` | Content repository | Issues (blog posts), trigger.yml (received via sync) |

### Core Components

```
src/escaping/
├── cli.py                 # BlogGenerator class - orchestrates the build
├── config.py              # Pydantic settings from config.yaml
├── services/
│   ├── github_service.py  # GitHub API wrapper with tenacity retry
│   └── render_service.py  # Jinja2 rendering, RSS/sitemap generation
└── utils/slug.py          # URL slug generator (Chinese→pinyin)
```

### Deployment Flow

```
Issue 更新 → geoqiao.github.io/trigger.yml
         → 发送 dispatch 到 escaping
         → escaping/gen_site.yml 生成网站
         → 直接 push 到 geoqiao.github.io main 分支
         → GitHub Pages 从 branch 自动部署
```

### Configuration System

Uses Pydantic models in `config.py` with `config.yaml` as the source. Follows **convention over configuration** principle with eight-section config:

**Core configs** (required):
- `github` - repo (username/repo format), username (auto-parsed from repo)
- `blog` - title, url, author
- `about` - avatar, bio, expertise, links

**Personalization configs** (optional, defaults provided):
- `branding` - show_powered_by, powered_by_text, powered_by_url, show_intro, intro_text, source_link_text, source_link_url
- `theme` - name (maps to templates/{name}, default: BearMinimal)

**Path configs** (optional, defaults provided):
- `paths` - output, theme, blog, tag, rss, about, page_size, home_post_count, language

**SEO configs** (optional):
- `seo` - google_search_console, enable_sitemap, enable_robots

**Comments config** (optional):
- `comments` - provider, repo, theme

**Security config** (optional):
- `security` - token_env

### Data Flow

1. `BlogGenerator.generate()` fetches issues via `GitHubService`
2. Generates slugs from issue titles (stable, readable URLs)
3. Renders Markdown to HTML via Marko (GFM + pangu)
4. Outputs HTML files via Jinja2 templates

### Output Structure

```
output/
├── index.html              # Landing page (home)
├── blog/
│   ├── index.html          # Blog list page
│   ├── page/1.html        # Paginated pages
│   └── {slug}.html        # Individual posts
├── tag/
│   ├── index.html          # Tag list
│   └── {tag}.html          # Tag pages
├── atom.xml                # RSS feed
├── sitemap.xml
├── robots.txt
└── about.html
```

## Common Commands

### Development

```bash
# Install dependencies
uv sync

# Set GitHub Token (required)
export G_T=ghp_xxxxx

# Generate site (repo from config.yaml)
uv run blog-gen

# Override repo (optional)
uv run blog-gen --repo username/other-repo

# Start local server (run from project root, NOT output/)
uv run python -m http.server 8000
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

### Testing (TDD Required)

```bash
# Run all tests with coverage
uv run pytest -v

# Run specific test file
uv run pytest tests/test_cli.py -v

# Run specific test class
uv run pytest tests/test_config.py::TestConfigLoading -v

# Run specific test method
uv run pytest tests/test_cli.py::test_blog_generator_integration -v

# Run with coverage report
uv run pytest --cov=src --cov-report=term-missing
```

### Code Quality

```bash
# Lint and fix
uv run ruff check --fix .

# Format
uv run ruff format .

# Type check
uv run ty
```

## Key Configuration

`config.yaml` (eight-section structure):

```yaml
# ============================================
# Core (required)
# ============================================
blog:
  title: "Blog Title"
  description: Short description
  url: https://example.com
  author: Your Name

github:
  repo: username/repo

about:
  avatar: https://example.com/avatar.jpg
  bio: |
    A short bio about yourself.
  expertise:
    - Python
    - DevOps
  links:
    - name: GitHub
      url: https://github.com/username

# ============================================
# Branding (optional)
# ============================================
# branding:
#   show_powered_by: true
#   powered_by_text: Powered by
#   powered_by_url: https://github.com
#   show_intro: true
#   intro_text: Welcome to my blog
#   source_link_text: View Source
#   source_link_url: https://github.com/username/username.github.io

# ============================================
# Theme (optional)
# ============================================
# theme:
#   name: BearMinimal

# ============================================
# Paths (optional)
# ============================================
# paths:
#   output: output
#   theme: BearMinimal
#   blog: blog
#   tag: tag
#   rss: atom.xml
#   about: about.html
#   page_size: 10
#   home_post_count: 10
#   language: en

# ============================================
# SEO (optional)
# ============================================
# seo:
#   google_search_console: ""
#   enable_sitemap: true
#   enable_robots: true

# ============================================
# Comments (optional)
# ============================================
# comments:
#   provider: utterances
#   repo: username/repo
#   theme: github-light

# ============================================
# Security (optional)
# ============================================
# security:
#   token_env: G_T
```

## Important Patterns

### TDD Workflow (Mandatory)

**Always write tests before code.**

```
Write test → Run (fails) → Write code → Run (passes) → Refactor
```

### Slug Generation

URLs follow `{number}-{slugified-title}` format:
- Chinese titles convert to pinyin: "数据分析" → "shu-ju-fen-xi"
- Max 60 characters, truncated at word boundaries

### Template Variables

Common context available in all templates (from `RenderService._get_common_context()`):
- `{{ blog_title }}`, `{{ blog_url }}`, `{{ author_name }}`
- `{{ github_name }}`, `{{ github_repo }}`
- `{{ theme_path }}` - Use for static assets (e.g., `/templates/BearMinimal`)
- `{{ rss_atom_path }}` - RSS feed filename
- `{{ meta_description }}` - Blog description
- `{{ google_search_verification }}` - Google Search Console verification code

### Theme Structure

Themes in `templates/{theme_name}/` must include:
- `base.html` - Base template with `{% block content %}`
- `home.html`, `post.html`, `tags.html`, `tag.html`, `about.html`
- `static/css/style.css` - Theme styles
- `static/js/theme.js` - Dark mode toggle (BearMinimal)

Static assets use absolute paths: `/templates/BearMinimal/static/css/style.css`

### GitHub Actions Deployment

**Dual-repo architecture**:

1. `trigger.yml` (in geoqiao.github.io):
   - Listens for issue events (opened, edited, comment created/edited)
   - Sends repository_dispatch to escaping

2. `gen_site.yml` (in escaping):
   - Receives dispatch, generates site
   - Pushes generated files to geoqiao.github.io main branch

**GitHub Pages deployment**:
- Must be configured as "Deploy from a branch" (not workflow)
- geoqiao.github.io Settings → Pages → Source: main branch, / (root)

Requires `G_T` secret (GitHub Personal Access Token with `repo` and `workflow` scopes).

## Themes

Single built-in theme: `BearMinimal` (clean, minimal design with dark mode toggle)

Switch themes by updating `config.yaml`:
```yaml
theme:
  name: BearMinimal
```

## Critical Notes

1. **Static Assets**: Templates use absolute paths `/templates/{ThemeName}/static/...`
2. **Security**: Jinja2 has `autoescape=True`, RSS uses CDATA
3. **Local Preview**: Must start server from project root (not output/)
4. **Theme Switching**: After switching themes in `config.yaml`, regenerate and copy static files. See "Local Preview Workflow" above.
5. **Mobile Comments**: Utterances comments (injected in `post.html` via `<script src="https://utteranc.es/client.js" ...>`) have iOS Safari compatibility handling with specific error messages for "Disable Cross-Site Tracking" setting
6. **Configuration**: Internal paths (`output/`, `blog/`, `atom.xml`) are now hardcoded; only customize site metadata and theme
7. **Dual-Repo**: Code lives in escaping, content (Issues) lives in geoqiao.github.io

## Task Execution

For multi-step or subagent-driven tasks, provide progress updates every 2-3 minutes or after completing each major milestone. If looping on the same files without clear progress, explicitly state what you're stuck on and ask for direction.

## Research and Data Tasks

When a user request involves external data (stock prices, market data, real-time info), immediately attempt web search or available data tools. Do not provide template frameworks or refuse due to policy without first trying to fetch actual data and presenting it neutrally.

## Skill Management

Before installing skills or plugins, verify the exact name exists in the registry. If installation fails, suggest 2-3 verified alternatives rather than continuing with troubleshooting a non-existent resource.
