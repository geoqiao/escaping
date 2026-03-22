# Blog Optimization Design

**Date:** 2026-03-22
**Status:** Approved
**Scope:** Full-stack optimization of geoqiao's GitHub Issues-based static blog

---

## Background

The blog is a custom Python static site generator (SSG) that:
- Uses GitHub Issues as the CMS
- Renders Jinja2 templates to static HTML
- Hosts on GitHub Pages
- Has a PaperMod-inspired theme with dark/light mode, CJK typography, Prism.js syntax highlighting, and utterances comments

The main pain points identified:
1. **Reading experience** — TOC doesn't track current section, no progress indicator, typography can be improved
2. **Content gaps** — code blocks lack copy button and language label; `about.html` is broken (no nav/SEO)
3. **Engineering quality** — no tests, full rebuild every time, no cache-busting on assets

---

## Goals

1. Improve the reading experience for every post page
2. Fix known bugs and content gaps
3. Make the build system more robust and faster
4. Keep all changes self-contained with no new external runtime dependencies (pure Python for backend, no Node.js required). Frontend JS libraries like Fuse.js are bundled locally and have no server-side or build-time impact.

---

## Non-Goals

- Rewriting the SSG in a different language or framework
- Adding a backend/server component
- Changing the GitHub Issues CMS workflow
- Redesigning the visual identity

---

## Architecture

The existing architecture is kept intact. All changes are additive or targeted replacements within existing files.

```
GitHub Issues (CMS)
       │
       ▼
  cli.py (build orchestrator)
       │
       ├── fetch issues via PyGitHub
       ├── [NEW] compare against build cache → skip unchanged issues
       ├── render Jinja2 templates
       ├── [NEW] fingerprint CSS/JS assets
       ├── [NEW] minify CSS/JS
       └── write HTML to contents/
```

Frontend changes are confined to:
- `templates/PaperMod/static/js/papermod.js` — TOC highlight, progress bar, code block enhancement
- `templates/PaperMod/static/css/papermod.css` — TOC highlight styles, progress bar styles, typography
- `templates/PaperMod/about.html` — fix to extend `base.html`
- `templates/PaperMod/post.html` — add progress bar element

Backend changes are confined to:
- `src/github_blog/cli.py` — incremental build logic, asset fingerprinting + minification orchestration
- `src/github_blog/services/render_service.py` — marko renderer extension (lazy-load images), feedgen RSS changes
- new `src/github_blog/build_cache.py` — incremental build cache helper
- new `src/github_blog/assets.py` — asset fingerprinting + minification helpers
- `tests/` — new test files

---

## Priority Breakdown

### P0 — Reading Experience Core

These changes directly affect every post page read.

#### TOC Active Highlight

**What:** As the user scrolls, the current section's heading is highlighted in the sticky TOC sidebar.

**How:**
- Use `IntersectionObserver` in `papermod.js` to watch all `h2`/`h3` elements inside `.post-content`
- When a heading enters the viewport (top ~20% threshold), mark the corresponding TOC `<a>` as `.toc-active`
- CSS: `.toc-active` gets `color: var(--accent)` and a left border accent

**Files:** `papermod.js`, `papermod.css`

#### Reading Progress Bar

**What:** A 2px-tall colored bar fixed at the top of the viewport that fills left-to-right as the user scrolls through a post.

**How:**
- Add `<div id="reading-progress"></div>` to `post.html` (before `</body>`)
- CSS: `position: fixed; top: 0; left: 0; height: 2px; background: var(--accent); width: 0%; z-index: 100; transition: width 0.1s`
- JS: `scroll` event listener updates `style.width` based on `scrollY / (documentHeight - viewportHeight) * 100`
- Only rendered in `post.html`, not on listing pages

**Files:** `post.html`, `papermod.js`, `papermod.css`

#### Typography Optimization

**What:** Improve readability of post body text.

**Changes:**
- `.post-content` max-width: `72ch` (currently unbounded within the content column)
- `line-height`: `1.8` (currently `1.6`)
- Paragraph `margin-bottom`: `1.25em`
- `h2`/`h3` in post body: clearer visual separation (border-bottom on `h2`, larger font-size delta)
- Blockquote: left border accent color, slightly indented

**Files:** `papermod.css`

---

### P1 — Content Enhancement + Bug Fixes

#### Code Block Enhancement

**What:** Each code block gets a language label (top-right corner) and a copy button (appears on hover).

**How:**
- In `papermod.js`, after DOMContentLoaded, query all `pre > code` elements
- Inject `<span class="code-lang">python</span>` from the element's class (e.g. `language-python`)
- Inject `<button class="copy-btn">Copy</button>`; on click, use `navigator.clipboard.writeText(pre.innerText)`, then briefly show "Copied!"
- CSS: `.code-lang` positioned top-right, small monospace text; `.copy-btn` hidden by default, visible on `pre:hover`

**Files:** `papermod.js`, `papermod.css`

#### Fix `about.html`

**What:** `about.html` currently doesn't extend `base.html`, so it has no nav, no dark mode support, no OG/Twitter tags, and no canonical URL.

**Fix:** Refactor `about.html` to `{% extends "base.html" %}` with appropriate `{% block %}` overrides for title, description, canonical, and body content.

**Files:** `templates/PaperMod/about.html`

#### Unit Tests

**What:** Cover the core logic that is currently untested.

**Test modules to create:**

| Test file | Coverage |
|-----------|----------|
| `tests/test_slug.py` | `slug.py` — CJK transliteration, ASCII slugify, collision handling |
| `tests/test_config.py` | `config.py` — required fields, env override, invalid config rejection |
| `tests/test_renderer.py` | Unit tests for `render_service.py` — call `render_post()`, `render_index()`, `render_tag()`, `render_home()` directly with minimal fixture data; assert the returned HTML string contains expected elements (no filesystem I/O) |
| `tests/test_pagination.py` | Pagination logic — page count, page boundaries, empty case |

**Tool:** `pytest`. Add to `pyproject.toml` dev dependencies.

**Files:** `tests/test_*.py`, `pyproject.toml`

#### Image Lazy Loading

**What:** All `<img>` tags in rendered post HTML get `loading="lazy"`.

**How:** Extend the marko renderer in `src/github_blog/services/render_service.py` — add a custom `Image` renderer class that injects `loading="lazy"` into the rendered `<img>` tag.

**Files:** `src/github_blog/services/render_service.py`

---

### P2 — Engineering Quality

#### Incremental Build

**What:** Skip re-rendering posts whose GitHub Issue `updated_at` hasn't changed since the last build.

**How:**
1. After each successful build, write `contents/.build-cache.json` — a dict mapping `issue_number → updated_at (ISO string)`
2. At build start, load this cache if it exists
3. For each fetched issue, compare `updated_at`; skip render if unchanged
4. Always re-render index, tag, and home pages (they depend on the full post list)
5. Always invalidate cache if `config.yaml` or any template changes (compare template mtimes)
6. Support a `--force` CLI flag in `cli.py` that bypasses the cache entirely and rebuilds all pages

**Files:** `src/github_blog/cli.py`, new `src/github_blog/build_cache.py`

#### Asset Fingerprinting

**What:** CSS and JS filenames include a content hash, e.g. `papermod.a3f9c1.css`, forcing browsers to fetch new versions when content changes.

**How:**
1. At build time, compute `md5(file_content)[:8]` for each static asset
2. Copy asset to `contents/static/css/papermod.<hash>.css`
3. Inject the hashed filename into a Jinja2 context variable (`asset_url('papermod.css')` helper)
4. Templates reference `{{ asset_url('papermod.css') }}`

**Files:** `src/github_blog/assets.py` (new helper), `src/github_blog/cli.py` (calls helper), and these templates that reference static assets: `base.html`, `home.html`, `about.html`

#### CSS/JS Minification

**What:** Reduce transfer size of static assets by ~30–40%.

**How:** Use `rcssmin` (CSS) and `rjsmin` (JS) — both are pure Python, zero new non-Python dependencies, compatible with the existing `uv` setup. Run at build time after fingerprinting inside `assets.py`.

**New dependencies:** `rcssmin`, `rjsmin` (add to `pyproject.toml`)

**Files:** `src/github_blog/assets.py` (new helper), `pyproject.toml`

---

### P3 — Advanced Features

#### Client-Side Full-Text Search

**What:** A search page (`/search.html`) with a text input that fuzzy-searches all post titles and content without a server.

**How:**
1. At build time, generate `contents/search-index.json` — array of `{title, url, tags, excerpt}` for all posts
2. `search.html` template loads Fuse.js (bundled locally, ~24 KB minified) and `search-index.json`
3. As the user types, Fuse.js filters results and updates the DOM
4. Add "Search" link to nav bar in `base.html`

**New dependency:** Fuse.js (bundled in `static/js/`, no CDN)

**Files:** `templates/PaperMod/search.html`, `src/github_blog/cli.py`, `base.html`, `static/js/fuse.min.js`

#### RSS Enhancement

**What:** Include full article content in the Atom feed (currently only excerpt/description). Add per-tag feeds at `/tag/{tag}/atom.xml`.

**How:** Update `feedgen` usage in the feed builder to set `entry.content()` with the full rendered HTML. Add a feed generation loop over all tags.

**Files:** `src/github_blog/services/render_service.py` (where feedgen is called)

#### Lighthouse Audit + Accessibility

**What:** Run a Lighthouse audit (Performance + Accessibility) against the live site and fix the top issues.

**Expected findings based on code review:**
- Missing `alt` attributes on some images → fix in marko renderer
- Low color contrast on some muted text → adjust CSS custom properties
- Missing `aria-label` on icon-only links (nav icons) → fix in `base.html`

**This is a one-time audit task, not a code change spec. It is excluded from the implementation plan and tracked separately.**

---

## Implementation Sequence

```
Week 1: P0 (TOC highlight, progress bar, typography)
Week 2: P1 (code blocks, about.html fix, tests, lazy images)
Week 3: P2 (incremental build, fingerprinting, minification)
Week 4+: P3 (search, RSS, Lighthouse) — optional, lower urgency
```

Each priority is independently deployable. P0 changes are purely frontend (no Python changes needed), so they can be deployed without touching the build pipeline.

---

## Risk & Trade-offs

| Risk | Mitigation |
|------|-----------|
| Incremental build misses a re-render | Cache invalidation includes config + template mtime check; `--force` flag bypasses cache |
| Asset fingerprinting breaks references | Centralized `asset_url()` helper — single place to update |
| Minification corrupts JS | Run tests after minification; keep unminified originals in `static/` for dev |
| Fuse.js search index grows large | Cap excerpt at 200 chars; index is ~50 KB for 50 posts — acceptable |

---

## Success Criteria

- [ ] P0: TOC highlights current section while scrolling through any post
- [ ] P0: Progress bar visible and accurate on all post pages
- [ ] P0: Typography changes applied, line-height and max-width verified
- [ ] P1: Copy button works on all code blocks; language label shows correctly
- [ ] P1: `/about.html` has nav, dark mode, and OG tags
- [ ] P1: `pytest` runs green with ≥ 80% line coverage across the four tested modules (`slug`, `config`, `render_service`, pagination logic)
- [ ] P2: Second build after a single issue edit only re-renders that post's page (all other post HTML files unchanged)
- [ ] P2: Build after touching any template file or `config.yaml` triggers a full rebuild (cache fully invalidated)
- [ ] P2: CSS/JS filenames contain hash; browser hard-refresh not needed after deploys
- [ ] P3: Search returns relevant results for title and content queries
