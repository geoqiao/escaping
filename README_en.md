# github-blog 🚀

> 中文版本: [README.md](./README.md)

## Introduction

`github-blog` is a minimalist and highly automated personal blog framework. It turns GitHub Issues into a powerful CMS, leverages GitHub Actions for automated builds, and deploys via GitHub Pages.

**Key Features**:

- 📝 **Issue-based Writing**: Write directly in GitHub Issues with label support.
- 🤖 **Zero-Ops Workflow**: No local setup required; build triggers automatically on issue updates.
- 🎨 **Elegant UI**: Built-in BearMinimal theme with dark mode support.
- 🔍 **SEO Ready**: Automated generation of `sitemap.xml`, `robots.txt`, and human-friendly slugs.
- ⚡ **High Performance**: Powered by Python 3.11 and `uv` for lightning-fast site generation.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│ github_blog (Code Repository - Source code lives here)      │
│                                                             │
│ ├── src/                  # Python source                   │
│ ├── templates/            # Theme templates (BearMinimal)    │
│ ├── .github/workflows/    # CI/CD workflows                 │
│ └── config.yaml           # Blog configuration              │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ gen_site.yml
                              │ (generates & pushes site)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ geoqiao.github.io (Content Repository - Issues only)         │
│                                                             │
│ ├── Issues              # Blog posts                        │
│ └── .github/workflows/  │                                   │
│     └── trigger.yml     │ Listens for Issue events          │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ trigger.yml
                              │ (triggers on Issue update)
                              │
                     ┌────────┴────────┐
                     │   GitHub Issues  │
                     │  (Your Editor)   │
                     └─────────────────┘
```

**Complete Flow**:

1. Create or edit an Issue in `geoqiao.github.io` (your blog post)
2. `trigger.yml` detects the event, sends dispatch to `github_blog`
3. `github_blog`'s `gen_site.yml` runs:
   - Fetches Issues
   - Generates static HTML
   - Pushes to `geoqiao.github.io` main branch
4. GitHub Pages detects the update, auto-deploys

---

## How to Use

### Method 1: Direct Use (Recommended)

1. **Fork the repo**: Fork `github-blog` to your GitHub account
2. **Configure GitHub Pages**:
   - Go to `Settings -> Pages`
   - Source: **Deploy from a branch**
   - Branch: **main**, Folder: **/ (root)**
3. **Add Secret**:
   - Go to `Settings -> Secrets and variables -> Actions`, add `G_T`
   - Value: your [GitHub Personal Access Token](https://github.com/settings/tokens) (needs `repo` and `workflow` scopes)
4. **Update config**: Edit `config.yaml` with your blog info
5. **Start writing**: Create Issues with labels, your blog goes live automatically

### Method 2: For Upstream Maintainers

```bash
# Clone repository
git clone https://github.com/geoqiao/github_blog.git
cd github_blog

# Install dependencies
uv sync

# Local preview
export G_T=your_token
uv run blog-gen
uv run python -m http.server 8000
```

---

## Configuration

Edit `config.yaml`:

```yaml
github:
  repo: username/username.github.io  # Your Issues repository

blog:
  title: My Blog
  url: https://username.github.io/
  author: Your Name

about:
  avatar: https://github.com/username.png
  bio: Your bio here
```

---

## Themes

Built-in theme: `BearMinimal` (clean, minimal design with dark mode)

---

## Live Demo

- **Author's Blog**: [geoqiao's Blog](https://geoqiao.github.io/)

---

## Credits

This project is inspired by:

- [gitblog](https://github.com/yihong0618/gitblog) - The pioneer of Issue-based blogging.
- [Gmeek](https://github.com/Meekdai/Gmeek) - For the minimalist build philosophy.
