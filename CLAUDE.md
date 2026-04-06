# github-blog

Python static blog generator using GitHub Issues as CMS. Renders to HTML with Jinja2, deployed to GitHub Pages.

**Live Demo:** https://geoqiao.github.io/

## Architecture

```
src/github_blog/
├── cli.py           # BlogGenerator
├── config.py        # Pydantic 8-section settings
├── services/
│   ├── github_service.py
│   └── render_service.py
└── utils/slug.py    # Chinese→pinyin slug generation

templates/Escape1/    # Single built-in theme
├── post.html
├── static/css/style.css
└── ...
```

**Dual-repo:** `escaping` (this repo, code) generates site → pushes to `geoqiao.github.io` (content repo).

## Common Commands

```bash
# Setup & run
uv sync
export G_T=ghp_xxxxx
uv run blog-gen                        # Generate site
uv run python -m http.server 8000      # Serve from project root

# Copy theme assets for local preview
cp -r templates/Escape1 output/templates/

# Test & quality (TDD required)
uv run pytest -v
uv run pytest tests/test_cli.py -v
uv run pytest --cov=src --cov-report=term-missing
uv run ruff check --fix .
uv run ruff format .
uv run ty
```

## Key Patterns

- **TDD Workflow:** Write test → Run (fails) → Write code → Run (passes) → Refactor
- **Slug format:** `{number}-{slugified-title}`, e.g. `1-shu-ju-fen-xi`
- **Template paths:** Absolute paths only — `/templates/Escape1/static/...`

## Configuration

See `config.example.yaml` for the full 8-section reference. Required sections:
- `blog` — title, url, author
- `github` — repo (`username/repo` format)
- `about` — avatar, bio, expertise, links

## Gotchas

1. **No global settings singleton.** `Settings` is explicitly injected into `BlogGenerator` and `RenderService`.
2. **Token env is dynamic.** `cli.py` reads `settings.security.token_env` at runtime; it is not hard-coded to `G_T`.
3. **Utterances lazy iframe bug.** `client.js` injects `loading="lazy"` iframe. On Safari with zero-height parents, `IntersectionObserver` may skip it and the `src` never loads. We monkey-patch `insertAdjacentHTML` in `post.html` to strip it.
4. **Comments theme auto-switching.** `comments.theme_mode: auto` follows the blog dark/light theme via `postMessage` and `MutationObserver` in `post.html`.
5. **Deploy from branch.** `geoqiao.github.io` Pages source must be `main` branch, `/ (root)`.
