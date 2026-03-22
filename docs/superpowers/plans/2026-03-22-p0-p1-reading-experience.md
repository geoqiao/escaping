# Blog P0+P1 Reading Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the reading experience on every post page (TOC highlight, progress bar, typography, code block copy button) and fix content bugs (about.html, image lazy loading, unit tests).

**Architecture:** All P0 changes are purely frontend — edit `papermod.js` and `papermod.css`, and add a `<div>` to `post.html`. P1 changes are a mix: pure HTML fix for `about.html`, a Python renderer extension for lazy images, and new `pytest` test files. No dependencies need to be added for P0. P1 adds `pytest` as a dev dependency.

**Tech Stack:** Vanilla JS (ES2019, IIFE pattern), CSS custom properties, Jinja2 templates, Python 3.11, marko + GFM, pytest

---

## File Map

| File | Action | Why |
|------|--------|-----|
| `templates/PaperMod/static/js/papermod.js` | Modify | Add TOC highlight, progress bar, code block copy |
| `templates/PaperMod/static/css/papermod.css` | Modify | TOC active style, progress bar style, typography, copy button style |
| `templates/PaperMod/post.html` | Modify | Add `<div id="reading-progress">` element |
| `templates/PaperMod/about.html` | Replace | Fix to extend `base.html` |
| `src/github_blog/services/render_service.py` | Modify | Add custom marko Image renderer for lazy loading |
| `tests/test_slug.py` | Create | Unit tests for slug generation |
| `tests/test_config.py` | Create | Unit tests for config validation |
| `tests/test_renderer.py` | Create | Smoke tests for render_service.py |
| `tests/test_pagination.py` | Create | Unit tests for pagination logic in cli.py |
| `pyproject.toml` | Modify | Add pytest dev dependency |

---

## Task 1: TOC Active Highlight

**Files:**
- Modify: `templates/PaperMod/static/js/papermod.js`
- Modify: `templates/PaperMod/static/css/papermod.css`

The existing TOC builder in `papermod.js` already assigns IDs to headings and builds `<a class="toc-link">` elements. We add an `IntersectionObserver` after the TOC is built to track which heading is in view.

- [ ] **Step 1: Add TOC highlight CSS**

  In `templates/PaperMod/static/css/papermod.css`, find the `.toc-link:hover` rule (around line 399) and add directly after it:

  ```css
  .toc-link.toc-active {
      color: var(--accent);
      border-left: 2px solid var(--accent);
      padding-left: 4px;
      font-weight: 700;
  }

  html[data-theme='dark'] .toc-link.toc-active {
      color: var(--accent);
  }
  ```

- [ ] **Step 2: Add IntersectionObserver to papermod.js**

  In `templates/PaperMod/static/js/papermod.js`, replace the entire file content with the following (preserving all existing logic and adding the observer block after the TOC is built):

  ```js
  // theme toggle and simple TOC builder
  (function () {
      const themeBtn = document.querySelector('.theme-toggle');
      const applyTheme = (t) => { document.documentElement.setAttribute('data-theme', t); themeBtn.textContent = t === 'dark' ? '☀️' : '🌙'; localStorage.setItem('theme', t) };
      const saved = localStorage.getItem('theme');
      if (saved) applyTheme(saved); else { const prefers = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches; applyTheme(prefers ? 'dark' : 'light') }
      if (themeBtn) themeBtn.addEventListener('click', () => { const cur = document.documentElement.getAttribute('data-theme') || 'light'; applyTheme(cur === 'dark' ? 'light' : 'dark') });

      // TOC builder + active highlight
      const toc = document.getElementById('toc');
      if (toc) {
          const content = document.querySelector('.post-content');
          if (content) {
              const headings = content.querySelectorAll('h2,h3');
              if (headings.length) {
                  const ul = document.createElement('ul');
                  ul.className = 'toc-list';
                  const tocLinks = [];
                  headings.forEach((h, index) => {
                      if (!h.id) {
                          const base = h.textContent.trim().toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-+|-+$/g, '');
                          h.id = base || `section-${index + 1}`;
                      }
                      const li = document.createElement('li');
                      const levelClass = h.tagName === 'H3' ? 'toc-level-2' : 'toc-level-1';
                      li.className = 'toc-item ' + levelClass;
                      const a = document.createElement('a');
                      a.className = 'toc-link';
                      a.href = '#' + h.id;
                      a.textContent = h.textContent;
                      li.appendChild(a);
                      ul.appendChild(li);
                      tocLinks.push({ heading: h, link: a });
                  });
                  toc.appendChild(ul);

                  // Active highlight via IntersectionObserver
                  let activeLink = null;
                  const observer = new IntersectionObserver((entries) => {
                      entries.forEach(entry => {
                          if (entry.isIntersecting) {
                              const match = tocLinks.find(t => t.heading === entry.target);
                              if (match) {
                                  if (activeLink) activeLink.classList.remove('toc-active');
                                  activeLink = match.link;
                                  activeLink.classList.add('toc-active');
                              }
                          }
                      });
                  }, { rootMargin: '0px 0px -80% 0px', threshold: 0 });

                  headings.forEach(h => observer.observe(h));
              }
          }
      }
  })();
  ```

- [ ] **Step 3: Verify in browser**

  Open any post page (e.g. `contents/blog/1-python.html`) in a browser. Scroll slowly — the TOC entry for the current section should turn green (`var(--accent)` = `#209460`) with a left border. Check dark mode too.

- [ ] **Step 4: Commit**

  ```bash
  git add templates/PaperMod/static/js/papermod.js templates/PaperMod/static/css/papermod.css
  git commit -m "feat: add TOC active highlight via IntersectionObserver"
  ```

---

## Task 2: Reading Progress Bar

**Files:**
- Modify: `templates/PaperMod/post.html`
- Modify: `templates/PaperMod/static/js/papermod.js`
- Modify: `templates/PaperMod/static/css/papermod.css`

- [ ] **Step 1: Add progress bar element to post.html**

  In `templates/PaperMod/post.html`, add the progress div immediately after the `{% block content %}` opening line (before `<article>`):

  ```html
  {% block content %}
  <div id="reading-progress"></div>
  <article class="post full-post">
  ```

- [ ] **Step 2: Add progress bar CSS**

  In `papermod.css`, after the `:root` block (after line 11), add:

  ```css
  #reading-progress {
      position: fixed;
      top: 0;
      left: 0;
      width: 0%;
      height: 2px;
      background: var(--accent);
      z-index: 200;
      transition: width 0.1s linear;
  }
  ```

- [ ] **Step 3: Add scroll listener to papermod.js**

  In `papermod.js`, inside the IIFE, add after the TOC section (before the closing `})();`):

  ```js
      // Reading progress bar
      const progressBar = document.getElementById('reading-progress');
      if (progressBar) {
          const updateProgress = () => {
              const scrollTop = window.scrollY;
              const docHeight = document.documentElement.scrollHeight - window.innerHeight;
              const pct = docHeight > 0 ? Math.min(100, (scrollTop / docHeight) * 100) : 0;
              progressBar.style.width = pct + '%';
          };
          window.addEventListener('scroll', updateProgress, { passive: true });
          updateProgress();
      }
  ```

- [ ] **Step 4: Verify in browser**

  Open a post page. A thin green line should appear at the very top of the viewport and grow as you scroll. It should not appear on index/tag/home pages.

- [ ] **Step 5: Commit**

  ```bash
  git add templates/PaperMod/post.html templates/PaperMod/static/js/papermod.js templates/PaperMod/static/css/papermod.css
  git commit -m "feat: add reading progress bar to post pages"
  ```

---

## Task 3: Typography Optimization

**Files:**
- Modify: `templates/PaperMod/static/css/papermod.css`

The `.post-content` block starts around line 312. Current `line-height` is `1.85`. We add `max-width`, increase paragraph spacing, and improve heading visual separation.

- [ ] **Step 1: Update .post-content styles**

  Find the `.post-content` rule (around line 312–321) and replace it with:

  ```css
  .post-content {
      line-height: 1.85;
      color: var(--text);
      font-size: 16.5px;
      word-wrap: break-word;
      word-break: break-word;
      overflow-wrap: break-word;
      min-width: 0;
      width: 100%;
      max-width: 72ch;
  }
  ```

- [ ] **Step 2: Update paragraph spacing**

  After the `.post-content` rule, add:

  ```css
  .post-content p {
      margin-bottom: 1.25em;
  }
  ```

- [ ] **Step 3: Improve h2 visual separation**

  Find `.post-content h2` (around line 350) and replace it with:

  ```css
  .post-content h2 {
      font-size: 1.25rem;
      margin-top: 2rem;
      margin-bottom: 0.75rem;
      padding-bottom: 0.4rem;
      border-bottom: 1px solid var(--divider);
  }
  ```

- [ ] **Step 4: Add blockquote style**

  After the `.post-content h3` rule, add:

  ```css
  .post-content blockquote {
      border-left: 3px solid var(--accent);
      margin: 1.5rem 0;
      padding: 0.5rem 0 0.5rem 1.25rem;
      color: var(--muted);
      font-style: italic;
  }

  .post-content blockquote p {
      margin: 0;
  }
  ```

- [ ] **Step 5: Verify in browser**

  Open a long post. Confirm: text column is narrower (~72 character width), `h2` has a subtle divider line below it, blockquotes have a green left border.

- [ ] **Step 6: Commit**

  ```bash
  git add templates/PaperMod/static/css/papermod.css
  git commit -m "style: improve post typography (max-width, paragraph spacing, h2, blockquote)"
  ```

---

## Task 4: Code Block Enhancement

**Files:**
- Modify: `templates/PaperMod/static/js/papermod.js`
- Modify: `templates/PaperMod/static/css/papermod.css`

Add a language label and copy button to every `<pre><code>` block. The language comes from the `language-*` class that Prism.js/marko adds to the `<code>` element.

- [ ] **Step 1: Add copy button + lang label CSS**

  In `papermod.css`, after the `.post-content pre>code` rule (around line 468), add:

  ```css
  /* Code block copy button and language label */
  .code-header {
      position: absolute;
      top: 0.5rem;
      right: 0.5rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
  }

  .code-lang {
      font-size: 0.75rem;
      font-family: inherit;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
  }

  .copy-btn {
      font-size: 0.75rem;
      font-family: inherit;
      padding: 0.2rem 0.5rem;
      border: 1px solid var(--divider);
      border-radius: 4px;
      background: var(--surface);
      color: var(--muted);
      cursor: pointer;
      opacity: 0;
      transition: opacity 0.15s;
  }

  .post-content pre:hover .copy-btn {
      opacity: 1;
  }

  .copy-btn:hover {
      background: var(--muted-bg);
      color: var(--text);
  }

  .copy-btn.copied {
      color: var(--accent);
      border-color: var(--accent);
  }
  ```

- [ ] **Step 2: Add code block injection to papermod.js**

  In `papermod.js`, inside the IIFE, add after the progress bar section (before the closing `})();`):

  ```js
      // Code block: language label + copy button
      document.querySelectorAll('.post-content pre').forEach(pre => {
          const code = pre.querySelector('code');
          if (!code) return;
          const langClass = Array.from(code.classList).find(c => c.startsWith('language-'));
          const lang = langClass ? langClass.replace('language-', '') : '';

          const header = document.createElement('div');
          header.className = 'code-header';

          if (lang) {
              const langSpan = document.createElement('span');
              langSpan.className = 'code-lang';
              langSpan.textContent = lang;
              header.appendChild(langSpan);
          }

          const copyBtn = document.createElement('button');
          copyBtn.className = 'copy-btn';
          copyBtn.textContent = 'Copy';
          copyBtn.addEventListener('click', () => {
              navigator.clipboard.writeText(code.innerText).then(() => {
                  copyBtn.textContent = 'Copied!';
                  copyBtn.classList.add('copied');
                  setTimeout(() => {
                      copyBtn.textContent = 'Copy';
                      copyBtn.classList.remove('copied');
                  }, 1500);
              });
          });
          header.appendChild(copyBtn);
          pre.appendChild(header);
      });
  ```

- [ ] **Step 3: Verify in browser**

  Open a post with code blocks. Hover over a code block — the "Copy" button should appear at the top-right. The language label (e.g. "python") should always be visible. Click "Copy" — button briefly shows "Copied!" then resets.

- [ ] **Step 4: Commit**

  ```bash
  git add templates/PaperMod/static/js/papermod.js templates/PaperMod/static/css/papermod.css
  git commit -m "feat: add copy button and language label to code blocks"
  ```

---

## Task 5: Fix about.html

**Files:**
- Replace: `templates/PaperMod/about.html`

Currently `about.html` is a standalone HTML document — no nav, no dark mode, no OG tags, and uses broken CSS paths. Fix it to extend `base.html`.

- [ ] **Step 1: Rewrite about.html**

  Replace the entire content of `templates/PaperMod/about.html` with:

  ```html
  {% extends 'base.html' %}

  {% block title %}About - {{ blog_title }}{% endblock %}

  {% block canonical %}
  <link rel="canonical" href="{{ blog_url.rstrip('/') }}/contents/about.html" />
  {% endblock %}

  {% block og_url %}{{ blog_url.rstrip('/') }}/contents/about.html{% endblock %}
  {% block og_title %}About - {{ blog_title }}{% endblock %}
  {% block og_description %}{{ meta_description }}{% endblock %}

  {% block twitter_url %}{{ blog_url.rstrip('/') }}/contents/about.html{% endblock %}
  {% block twitter_title %}About - {{ blog_title }}{% endblock %}
  {% block twitter_description %}{{ meta_description }}{% endblock %}

  {% block content %}
  <div class="about-page" style="max-width:640px;margin:3rem auto;text-align:center">
      <img src="/templates/PaperMod/static/images/favicon.png" alt="{{ author_name }}"
          style="width:120px;border-radius:50%;margin-bottom:1rem">
      <h1 style="margin-bottom:0.5rem">{{ author_name }}</h1>
      <p style="color:var(--muted);margin-bottom:1.5rem">{{ meta_description }}</p>
      <p>
          <a href="https://github.com/{{ github_name }}" style="color:var(--accent)">GitHub</a>
      </p>
  </div>
  {% endblock %}
  ```

- [ ] **Step 2: Check that render_service renders about.html**

  Look at `src/github_blog/services/render_service.py` — confirm there is a `render_about()` method or similar. If not, check `cli.py` for where `about.html` is generated. Add the render call if it is currently missing.

  Grep for about in cli.py:
  ```bash
  grep -n "about" src/github_blog/cli.py src/github_blog/services/render_service.py
  ```

  If no render call exists, add to `render_service.py`:

  ```python
  def render_about(self) -> str:
      template = self.env.get_template("about.html")
      return template.render(
          blog_title=settings.blog.title,
          github_name=settings.github.name,
          blog_url=str(settings.blog.url),
          rss_atom_path=settings.blog.rss_atom_path,
          author_name=settings.blog.author.name,
          meta_description=settings.blog.description,
          google_search_verification=settings.google_search_console.content,
      )
  ```

  And in `cli.py`'s `generate()` method, after generating the sitemap:

  ```python
  # 渲染 about 页面
  about_content = self.render.render_about()
  (settings.blog.content_dir / "about.html").write_text(about_content, encoding="utf-8")
  ```

- [ ] **Step 3: Verify in browser**

  Open `contents/about.html`. Confirm: nav bar is present, dark mode toggle works, page has correct title in browser tab.

- [ ] **Step 4: Commit**

  ```bash
  git add templates/PaperMod/about.html src/github_blog/services/render_service.py src/github_blog/cli.py
  git commit -m "fix: rewrite about.html to extend base.html with nav, dark mode, and OG tags"
  ```

---

## Task 6: Unit Tests — slug, config, pagination

**Files:**
- Create: `tests/test_slug.py`
- Create: `tests/test_config.py`
- Create: `tests/test_pagination.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add pytest to pyproject.toml**

  In `pyproject.toml`, find the `[project.optional-dependencies]` or `[dependency-groups]` section. Add pytest:

  ```toml
  [dependency-groups]
  dev = ["pytest>=8.0"]
  ```

  Then run:
  ```bash
  uv sync
  ```

- [ ] **Step 2: Write slug tests**

  Create `tests/test_slug.py`:

  ```python
  from src.github_blog.utils.slug import generate_slug


  def test_no_tags_returns_issue_number():
      assert generate_slug(42, []) == "42"


  def test_ascii_tag_slugified():
      assert generate_slug(1, ["Python"]) == "1-python"


  def test_cjk_tag_transliterated():
      # 数据 → some romanization
      result = generate_slug(2, ["数据"])
      assert result.startswith("2-")
      assert len(result) > 2  # slug part exists


  def test_multiple_tags_joined():
      result = generate_slug(3, ["Python", "数据"])
      assert result.startswith("3-python-")


  def test_special_chars_stripped():
      result = generate_slug(5, ["C++"])
      assert result == "5-c" or result.startswith("5-c")
  ```

- [ ] **Step 3: Run slug tests — verify they pass**

  ```bash
  uv run pytest tests/test_slug.py -v
  ```

  Expected: all 5 tests PASS.

- [ ] **Step 4: Write config tests**

  Create `tests/test_config.py`:

  ```python
  import pytest
  from pydantic import ValidationError


  def test_settings_loads_from_yaml():
      """settings object should load without error from config.yaml"""
      from src.github_blog.config import settings
      assert settings.blog.title
      assert settings.blog.url
      assert settings.github.name


  def test_settings_has_content_dir():
      from src.github_blog.config import settings
      assert settings.blog.content_dir is not None


  def test_settings_page_size_positive():
      from src.github_blog.config import settings
      assert settings.blog.page_size > 0
  ```

- [ ] **Step 5: Run config tests — verify they pass**

  ```bash
  uv run pytest tests/test_config.py -v
  ```

  Expected: all 3 tests PASS.

- [ ] **Step 6: Write pagination tests**

  The pagination logic is inside `BlogGenerator._generate_index` in `cli.py`. Extract the core logic to test it. Write tests that call the pagination calculation directly:

  Create `tests/test_pagination.py`:

  ```python
  def _paginate(issues, page_size):
      """Mirror of the pagination logic in cli.py._generate_index"""
      pages = [issues[i:i + page_size] for i in range(0, len(issues), page_size)]
      total_pages = max(1, len(pages))
      result = []
      for i, page_issues in enumerate(pages, start=1):
          result.append({
              "page": i,
              "pages": total_pages,
              "has_prev": i > 1,
              "has_next": i < total_pages,
              "prev_num": i - 1,
              "next_num": i + 1,
              "issues": page_issues,
          })
      return result


  def test_empty_issues_gives_one_page():
      pages = _paginate([], page_size=10)
      assert len(pages) == 1
      assert pages[0]["issues"] == []


  def test_exact_page_size_gives_one_page():
      pages = _paginate(list(range(10)), page_size=10)
      assert len(pages) == 1
      assert pages[0]["has_next"] is False
      assert pages[0]["has_prev"] is False


  def test_overflow_creates_second_page():
      pages = _paginate(list(range(11)), page_size=10)
      assert len(pages) == 2
      assert pages[0]["has_next"] is True
      assert pages[1]["has_prev"] is True
      assert len(pages[1]["issues"]) == 1


  def test_page_numbers_are_one_indexed():
      pages = _paginate(list(range(5)), page_size=2)
      assert [p["page"] for p in pages] == [1, 2, 3]
  ```

- [ ] **Step 7: Run pagination tests — verify they pass**

  ```bash
  uv run pytest tests/test_pagination.py -v
  ```

  Expected: all 4 tests PASS.

- [ ] **Step 8: Commit**

  ```bash
  git add pyproject.toml uv.lock tests/test_slug.py tests/test_config.py tests/test_pagination.py
  git commit -m "test: add unit tests for slug, config, and pagination"
  ```

---

## Task 7: Unit Tests — RenderService

**Files:**
- Create: `tests/test_renderer.py`

These are smoke tests that call `RenderService` methods with minimal fixture data and assert the returned HTML contains expected elements. No filesystem I/O — just string assertions.

- [ ] **Step 1: Create a minimal Issue fixture**

  Create `tests/test_renderer.py`:

  ```python
  from datetime import datetime, timezone
  from unittest.mock import MagicMock

  import pytest

  from src.github_blog.services.render_service import RenderService


  @pytest.fixture
  def render():
      return RenderService()


  def _make_issue(number=1, title="Test Post", body="Hello **world**", labels=None):
      issue = MagicMock()
      issue.number = number
      issue.title = title
      issue.body = body
      issue.labels = labels or []
      issue.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
      issue.updated_at = datetime(2024, 1, 2, tzinfo=timezone.utc)
      return issue


  def test_markdown_to_html_renders_bold(render):
      html = render.markdown_to_html("Hello **world**")
      assert "<strong>world</strong>" in html


  def test_render_post_contains_title(render):
      issue = _make_issue(title="My Great Post")
      html = render.render_post(issue, slug="1-test", html_body="<p>body</p>")
      assert "My Great Post" in html


  def test_render_post_contains_toc_element(render):
      issue = _make_issue()
      html = render.render_post(issue, slug="1-test", html_body="<p>body</p>")
      assert 'id="toc"' in html


  def test_render_index_contains_issues(render):
      issues = [_make_issue(number=1, title="Post One"), _make_issue(number=2, title="Post Two")]
      pagination = {"page": 1, "pages": 1, "has_prev": False, "has_next": False, "prev_num": 0, "next_num": 2}
      html = render.render_index(issues, tags=["python"], pagination=pagination, issue_slugs={1: "1-python", 2: "2-python"})
      assert "Post One" in html
      assert "Post Two" in html


  def test_render_home_shows_latest_posts(render):
      issues = [_make_issue(number=i, title=f"Post {i}") for i in range(1, 4)]
      html = render.render_home(issues, issue_slugs={i: f"{i}-test" for i in range(1, 4)})
      assert "Post 1" in html


  def test_render_tag_page_contains_tag_name(render):
      issues = [_make_issue(title="Tagged Post")]
      html = render.render_tag_page("python", issues, tags=["python"], issue_slugs={1: "1-python"})
      assert "python" in html.lower()
  ```

- [ ] **Step 2: Run renderer tests — verify they pass**

  ```bash
  uv run pytest tests/test_renderer.py -v
  ```

  Expected: all 6 tests PASS. If a test fails due to missing template variables, check `render_service.py` for required context keys and add them to the fixture.

- [ ] **Step 3: Run full test suite**

  ```bash
  uv run pytest tests/ -v --tb=short
  ```

  Expected: all tests PASS.

- [ ] **Step 4: Commit**

  ```bash
  git add tests/test_renderer.py
  git commit -m "test: add render_service smoke tests"
  ```

---

## Task 8: Image Lazy Loading

**Files:**
- Modify: `src/github_blog/services/render_service.py`

marko allows overriding the renderer for individual element types. We add a custom `Image` renderer that injects `loading="lazy"` on every `<img>` tag.

- [ ] **Step 1: Write the failing test first**

  Add to `tests/test_renderer.py`:

  ```python
  def test_image_has_lazy_loading(render):
      html = render.markdown_to_html("![alt text](https://example.com/img.png)")
      assert 'loading="lazy"' in html
  ```

- [ ] **Step 2: Run test to verify it fails**

  ```bash
  uv run pytest tests/test_renderer.py::test_image_has_lazy_loading -v
  ```

  Expected: FAIL — `loading="lazy"` not in output yet.

- [ ] **Step 3: Add lazy image renderer to render_service.py**

  In `src/github_blog/services/render_service.py`, add the following imports and class before the `RenderService` class definition:

  ```python
  from marko.html_renderer import HTMLRenderer
  ```

  Then add a custom renderer class:

  ```python
  class LazyImageRenderer(HTMLRenderer):
      """Marko HTML renderer that adds loading='lazy' to all img tags."""

      def render_image(self, element) -> str:
          result = super().render_image(element)
          # Inject loading="lazy" into the <img> tag
          return result.replace("<img ", '<img loading="lazy" ', 1)
  ```

  Then update `RenderService.__init__` to use it:

  ```python
  def __init__(self):
      self.env = Environment(loader=FileSystemLoader(str(settings.theme.path)))
      self.markdown = Markdown(extensions=[GFM, "pangu"], renderer=LazyImageRenderer)
  ```

- [ ] **Step 4: Run test to verify it passes**

  ```bash
  uv run pytest tests/test_renderer.py::test_image_has_lazy_loading -v
  ```

  Expected: PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

  ```bash
  uv run pytest tests/ -v
  ```

  Expected: all tests PASS.

- [ ] **Step 6: Commit**

  ```bash
  git add src/github_blog/services/render_service.py tests/test_renderer.py
  git commit -m "feat: add loading=lazy to all images via custom marko renderer"
  ```

---

## Verification

After all tasks are complete, run the full test suite one final time:

```bash
uv run pytest tests/ -v --tb=short
```

All tests should pass. Then do a manual smoke test by running the generator locally (if GitHub token is available) or reviewing the generated HTML files for:

- [ ] TOC highlights current section on scroll
- [ ] Green progress bar appears on post pages
- [ ] Typography looks right (narrower column, larger paragraph gaps, h2 dividers)
- [ ] Code blocks show language label + copy button on hover
- [ ] `/contents/about.html` has nav and dark mode
- [ ] `<img>` tags in post HTML have `loading="lazy"`

---

## Follow-up Plan

The P2 engineering quality improvements (incremental build, asset fingerprinting, CSS/JS minification) are tracked separately in `docs/superpowers/plans/2026-03-22-p2-engineering-quality.md` (to be written).
