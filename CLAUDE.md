# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`github-blog` is a Python-based static blog generator that uses GitHub Issues as a CMS. It generates static HTML files from Issues and deploys to GitHub Pages.

## Architecture

### Core Components

- **`src/github_blog/cli.py`** - Entry point with `BlogGenerator` class that orchestrates the entire generation pipeline
- **`src/github_blog/config.py`** - Pydantic-based configuration loaded from `config.yaml`
- **`src/github_blog/services/github_service.py`** - GitHub API integration using PyGithub with retry logic
- **`src/github_blog/services/render_service.py`** - Markdown→HTML conversion (via Marko), RSS/Atom feed, sitemap, and robots.txt generation
- **`src/github_blog/utils/slug.py`** - SEO-friendly URL slug generation with Chinese pinyin support

### Data Flow

1. `BlogGenerator.generate()` fetches Issues from GitHub (filtered by creator)
2. Generates slugs for each Issue using pinyin conversion for Chinese tags
3. Renders markdown to HTML with lazy-loading images
4. Outputs: individual post pages, paginated index, tag pages, home page, RSS feed, sitemap, robots.txt

### Template System

Templates use Jinja2. Two themes available:
- `templates/PaperMod/` - Default theme (Hugo PaperMod port)
- `templates/default_theme/` - Legacy theme

Template path is configured in `config.yaml` under `theme.path`.

## Development Commands

### Setup
```bash
# Install dependencies (uses uv)
uv sync

# Install dev dependencies
uv sync --group dev
```

### Running
```bash
# Generate blog locally (requires GitHub token)
uv run blog-gen <GITHUB_TOKEN> <REPO_NAME>

# Example
uv run blog-gen ghp_xxx geoqiao/geoqiao.github.io
```

### Local Preview

**Important:** Always start the HTTP server from the project root directory, not from `contents/`.

```bash
# Correct: Start from project root
uv run python -m http.server 8000
# Then open http://localhost:8000
```

**Why:** The project uses absolute paths like `/templates/PaperMod/static/css/papermod.css` for CSS.
- The `templates/` directory is at the project root
- `contents/` is just a subdirectory for blog posts
- Starting from `contents/` would cause 404 errors for all static resources

**Directory structure reminder:**
```
project-root/          <- Start server here
├── index.html         <- Landing page (home)
├── contents/          <- Blog posts subdirectory
│   └── blog/
└── templates/         <- Theme static files
```

### Testing
```bash
# Run all tests with coverage
uv run pytest

# Run specific test file
uv run pytest tests/test_config.py

# Run with verbose output
uv run pytest -v
```

### Linting & Type Checking
```bash
# Run ruff linter
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .

# Format code
uv run ruff format .

# Type check (requires pyright installed)
pyright
```

## Configuration

All configuration is in `config.yaml`:

```yaml
blog:
  title: "Blog Title"
  description: "Description"
  url: "https://username.github.io/"
  content_dir: "./contents/"      # Output directory for generated files
  blog_dir: "blog/"               # Subdirectory for posts
  rss_atom_path: "atom.xml"
  author:
    name: "Author Name"
    email: "email@example.com"
  page_size: 10                   # Posts per page

github:
  name: "username"                # GitHub username
  repo: "username/repo"           # Source repo for Issues

GoogleSearchConsole:
  content: "verification_code"    # GSC verification
  verify: true

theme:
  path: "templates/PaperMod"      # Theme directory
```

## Key Dependencies

- **PyGithub** - GitHub API client
- **Marko** - Markdown parser with GFM and pangu extensions
- **Jinja2** - Template engine
- **feedgen** - RSS/Atom generation
- **pypinyin** - Chinese to pinyin conversion for slugs
- **pydantic-settings** - Configuration management
- **tenacity** - Retry logic for GitHub API calls

## Project Structure

```
├── src/github_blog/          # Main source code
│   ├── cli.py               # CLI entry point
│   ├── config.py            # Configuration models
│   ├── services/            # Business logic
│   │   ├── github_service.py
│   │   └── render_service.py
│   └── utils/               # Utilities
│       └── slug.py
├── templates/               # Jinja2 templates
│   ├── PaperMod/           # Default theme
│   ├── default_theme/      # Legacy theme
│   └── seo/                # SEO templates (sitemap, robots)
├── tests/                   # Test files
├── config.yaml             # Blog configuration
└── pyproject.toml          # Package metadata & tool config
```

## GitHub Actions Workflow

The `.github/workflows/gen_site.yml` workflow:
1. Triggers on: issue events, issue_comment events, push to main
2. Runs `blog-gen` to generate static files
3. Uploads to GitHub Pages artifact
4. Deploys to GitHub Pages

Requires `G_T` secret (GitHub Personal Access Token) with repo access.

## Notes

- Generated files (`contents/`, `index.html`, `sitemap.xml`, `robots.txt`) are gitignored; they are built fresh in CI
- The blog fetches only Issues created by the authenticated user (via `creator=me` filter)
- Slugs are generated as `{issue_number}-{tag1}-{tag2}` with Chinese tags converted to pinyin
- The project uses `uv` for fast Python package management, not pip
