# Migration Guide: Config Refactor

This is a breaking change. Follow these steps to migrate from the old config format to the new strict structure.

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

The old `config.yaml` format is no longer supported. You must migrate to the new strict structure.

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
  source_code_text: "View Source ->"
  source_code_url: "https://github.com/..."
  recent_posts_title: "Recent Posts"
  view_all_text: "View all posts ->"
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
  next_text: "Next ->"

tags:
  page_title: "Tags"
```

**New Structure (required):**
```yaml
# ============================================
# Core (required)
# ============================================
github:
  repo: username/username.github.io
  allowed_authors:
    - username

site:
  title: "Blog Title"
  url: https://username.github.io/
  author: Your Name
  description: A short description
  language: en
  # navigation:          # optional
  #   items:
  #     - name: Blog
  #       url: /blog/
  #     - name: Tags
  #       url: /tag/
  #     - name: About
  #       url: /about.html
  #     - name: RSS
  #       url: /atom.xml

profile:
  avatar: https://github.com/username.png
  bio: |
    A short bio about yourself.
  links:
    - name: GitHub
      url: https://github.com/username

about:
  issue_number: 1

security:
  token_env: G_T

# ============================================
# Branding (optional)
# ============================================
branding:
  show_powered_by: true
  powered_by_text: escaping
  powered_by_url: https://github.com/username/escaping
  show_intro: true
  intro_text: This is a static blog system based on GitHub Issues.
  intro_text2: Generated with Python + Jinja2, deployed via GitHub Actions.
  source_link_text: View source code ->
  source_link_url: https://github.com/username/escaping

# ============================================
# Paths (optional)
# ============================================
paths:
  output: output
  theme: Escape1
  blog: blog
  tag: tag
  rss: atom.xml
  about: about.html
  page: page
  page_size: 10

# ============================================
# SEO (optional)
# ============================================
seo:
  google_search_console: ""
  enable_sitemap: true
  enable_robots: true

# ============================================
# Comments (optional)
# repo falls back to github.repo when empty
# theme_mode: auto follows the blog theme
# ============================================
comments:
  provider: utterances
  repo: ""
  theme: github-light
  theme_mode: auto
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
   - Set `github.allowed_authors` to your GitHub username
   - Set `site.title`, `site.url`, `site.author`, `site.description`
   - Set `profile.avatar`, `profile.bio`, `profile.links`
   - Set `about.issue_number` to the Issue number for your About page
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
| `blog.content_dir` | Internal path, now in `paths.output` |
| `blog.blog_dir` | Internal path, now in `paths.blog` |
| `blog.rss_atom_path` | Internal path, now in `paths.rss` |
| `blog.author.email` | Not used in templates |
| `GoogleSearchConsole` | Use `seo.google_search_console` instead |
| `theme.path` | Internal path, now uses `paths.theme` |
| `theme.seo` | Removed (SEO is now automatic) |
| `home.*` | Replaced with `branding.*` and `profile.*` |
| `about.page_title` | Now uses `site.title` |
| `about.sections` | About narrative is now Issue-authored; profile data is in `profile` |
| `about.expertise` | Removed; expertise belongs to About Issue Content |
| `navigation` | Now under `site.navigation` |
| `pagination.*` | Removed (pagination is automatic) |
| `tags.page_title` | Now uses `site.title` |
| `blog.*` (top-level) | Replaced by `site.*` for identity and `profile.*` for profile |
| `github.name` | Derived from `github.repo` |

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

## Internal Paths

The following paths are configurable via `paths.*` but have safe defaults:

- `output/` - Site output directory (must be in the allowed output-root set)
- `blog/` - Blog post directory
- `tag/` - Tag pages directory
- `atom.xml` - RSS feed filename
- `about.html` - About page filename

Customize `paths.theme` to use a different theme directory (e.g., `Escape1` or `Escape2`).
