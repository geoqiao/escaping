# Migration Guide: Config Refactor

This is a breaking change. Follow these steps to migrate from the old config format to the new three-tier structure.

## What's Changed

### CLI Usage

**Before:**
```bash
uv run blog-gen $G_T $REPO
# Example: uv run blog-gen ghp_xxxxx geoqiao/geoqiao.github.io
```

**After:**
```bash
# Set token via environment variable
export G_T=ghp_xxxxx

# Run without arguments (repo is read from config.yaml)
uv run blog-gen

# Or override repo via CLI flag
uv run blog-gen --repo username/other-repo
```

For CI/CD (GitHub Actions), `G_T` is automatically available as a secret environment variable.

### config.yaml Structure

The old `config.yaml` format is no longer supported. You must migrate to the new structure.

**Old Structure (unsupported):**
```yaml
blog:
  title: "Blog Title"
  description: "A short description"
  url: https://username.github.io/
  content_dir: "./output/"
  blog_dir: "blog/"
  rss_atom_path: "atom.xml"
  author:
    name: Your Name
    email: your.email@example.com
  page_size: 10

github:
  name: username
  repo: username/username.github.io

GoogleSearchConsole:
  content: ""
  verify: false

theme:
  path: "templates/BearMinimal"
  seo: "templates/seo"

home:
  intro_line1: "..."
  intro_line2: "..."
  source_code_text: "View Source →"
  source_code_url: "https://github.com/..."
  recent_posts_title: "Recent Posts"
  view_all_text: "View all posts →"
  post_count: 10

about:
  page_title: "About"
  sections:
    - title: "About Me"
      type: "paragraphs"
      content: []

navigation:
  items:
    - name: "Blog"
      url: "/blog/"

pagination:
  prev_text: "← Prev"
  next_text: "Next →"

tags:
  page_title: "Tags"
```

**New Structure (required):**
```yaml
# ============================================
# Core (required)
# ============================================
github:
  repo: username/repo

blog:
  title: "Blog Title"
  url: https://username.github.io/
  author: Your Name

about:
  avatar: https://github.com/username.png
  bio: |
    A short bio about yourself.
  expertise:
    - Python
    - DevOps
  links:
    - name: GitHub
      url: https://github.com/username
    - name: Twitter/X
      url: https://twitter.com/username

# ============================================
# Personalization (optional)
# ============================================
branding:
  show_powered_by: true
  powered_by_text: escaping
  powered_by_url: https://github.com/username/escaping
  show_intro: true
  intro_text: This is a static blog system based on GitHub Issues.
  source_link_text: View source code →
  source_link_url: https://github.com/username/escaping

# ============================================
# Advanced (optional)
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
  language: en

# ============================================
# SEO (optional)
# ============================================
seo:
  google_search_console: ""
  enable_sitemap: true
  enable_robots: true

# ============================================
# Comments (optional)
# ============================================
comments:
  provider: utterances
  repo: username/repo
  theme: github-light

# ============================================
# Security (optional)
# ============================================
security:
  token_env: G_T
```

## Migration Steps

1. **Backup your current `config.yaml`**
   ```bash
   cp config.yaml config.yaml.backup
   ```

2. **Create a new config from the template**
   ```bash
   cp config.example.yaml config.yaml
   ```

3. **Copy over your personal information**
   - Set `github.repo` to your repository (e.g., `username/username.github.io`)
   - Set `blog.title`, `blog.url`, `blog.author`
   - Set `about.avatar`, `about.bio`, `about.expertise`, `about.links`
   - Set `seo.google_search_console` if you have a verification code

4. **Set `G_T` environment variable**
   ```bash
   export G_T=ghp_xxxxx  # Your GitHub Personal Access Token
   ```

5. **Test the migration**
   ```bash
   uv run blog-gen
   ```

## Removed Features

The following old config sections are **no longer supported**:

| Old Section | Reason |
|-------------|--------|
| `blog.content_dir` | Internal path, now hardcoded to `output/` |
| `blog.blog_dir` | Internal path, now hardcoded to `blog/` |
| `blog.rss_atom_path` | Internal path, now hardcoded to `atom.xml` |
| `blog.author.email` | Not used in templates |
| `GoogleSearchConsole` | Use `seo.google_search_console` instead |
| `theme.path` | Internal path, now uses `paths.theme` |
| `theme.seo` | Removed (SEO is now automatic) |
| `home.*` | Replaced with `branding.*` and `about.*` |
| `about.page_title` | Now uses `blog.title` |
| `about.sections` | Restructured to `about.bio`, `about.expertise`, `about.links` |
| `navigation` | Now auto-generated with defaults |
| `pagination.*` | Removed (pagination is automatic) |
| `tags.page_title` | Now uses `blog.title` |

## Custom Themes

If you have a custom theme, update templates to use the new variable names:

### Branding Variables

Old variables in `home` section are now in `branding`:

| Old Variable | New Variable |
|--------------|--------------|
| `{{ home.source_code_text }}` | `{{ branding.source_link_text }}` |
| `{{ home.source_code_url }}` | `{{ branding.source_link_url }}` |
| `{{ home.intro_line1 }}` | `{{ branding.intro_text }}` |

### Footer Branding

In your `base.html` footer, update:

```html
<!-- Old -->
<p>&copy; {{ author_name }}{% if show_powered_by %} · powered by <a href="{{ powered_by_url }}">{{ powered_by_text }}</a>{% endif %}</p>

<!-- New -->
<p>&copy; {{ author_name }}{% if branding.show_powered_by %} · powered by <a href="{{ branding.powered_by_url }}">{{ branding.powered_by_text }}</a>{% endif %}</p>
```

### Comment System

In your `post.html`, the utterances script now uses `comments` instead of hardcoded values:

```html
<!-- Old -->
<script src="https://utteranc.es/client.js"
        repo="username/repo"
        theme="github-light">

<!-- New -->
<script src="https://utteranc.es/client.js"
        repo="{{ comments.repo }}"
        theme="{{ comments.theme }}">
```

## Internal Paths (Now Hardcoded)

The following paths are now hardcoded and should not be configured:

- `output/` - Site output directory
- `blog/` - Blog post directory
- `tag/` - Tag pages directory
- `atom.xml` - RSS feed filename
- `about.html` - About page filename

Only customize `paths.theme` if you have a custom theme directory.
