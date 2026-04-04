# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`github-blog` is a Python-based static blog generator that uses GitHub Issues as a CMS. It fetches issues via GitHub API, renders them to HTML using Jinja2 templates, and generates SEO-friendly outputs (sitemap, RSS, robots.txt).

**Live Demo:** https://geoqiao.github.io/

## Architecture

### Core Components

```
src/github_blog/
├── cli.py                 # BlogGenerator class - orchestrates the build
├── config.py              # Pydantic settings from config.yaml
├── services/
│   ├── github_service.py  # GitHub API wrapper with tenacity retry
│   └── render_service.py  # Jinja2 rendering, RSS/sitemap generation
└── utils/slug.py          # URL slug generator (Chinese→pinyin)
```

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
│   ├── page/1.html         # Paginated pages
│   └── {slug}.html         # Individual posts
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

# Run blog generator locally (requires GitHub Token)
uv run blog-gen <TOKEN> <REPO>        # e.g., uv run blog-gen ghp_xxx geoqiao/geoqiao.github.io

# Start local server (run from project root, NOT output/)
uv run python -m http.server 8000
```

### Testing (TDD Required)

```bash
# Run all tests with coverage
uv run pytest -v

# Run specific test file
uv run pytest tests/test_cli.py -v

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

`config.yaml`:

```yaml
blog:
  title: "Blog Title"
  url: https://example.com
  content_dir: "./output/"      # Build output path
  blog_dir: "blog/"             # Article subdirectory
  page_size: 10                 # Posts per page

github:
  name: username
  repo: user/repo

theme:
  path: "templates/PaperMint"   # Theme directory
  seo: "templates/seo"          # SEO templates
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
- `{{ theme_path }}` - Use for static assets
- `{{ rss_atom_path }}` - RSS feed filename
- `{{ meta_description }}` - Blog description
- `{{ google_search_verification }}` - Google Search Console verification code

### GitHub Actions Deployment

Workflow (`.github/workflows/gen_site.yml`) triggers on:
- Issue created/edited
- Issue comment created/edited
- Push to main

Requires `G_T` secret (GitHub Personal Access Token).

## Critical Notes

1. **Path Handling**: Use `config.yaml` paths, avoid `Path.resolve()` (breaks CI)
2. **Static Assets**: Templates use absolute paths `/templates/PaperMint/static/...`
3. **Security**: Jinja2 has `autoescape=True`, RSS uses CDATA
4. **Local Preview**: Must start server from project root (not output/)
