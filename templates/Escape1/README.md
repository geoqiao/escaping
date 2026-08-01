# Escape1 Theme

A minimal, clean, and configurable blog theme for github-blog.

## Features

- **Minimalist Design** - Clean layout with focus on content
- **Dark Mode** - Toggle between light and dark themes
- **Responsive** - Works great on desktop and mobile
- **Fast** - No external dependencies except Utterances for comments
- **Accessible** - Good contrast and semantic HTML
- **Configurable** - All text and links via config.yaml

## Quick Start

1. Copy `config.example.yaml` to `config.yaml` and customize
2. Set your theme in config.yaml:
   ```yaml
   paths:
     theme: Escape1
   ```
3. Run the generator:
   ```bash
   export G_T=ghp_xxxxx
   uv run blog-gen
   ```

## Configuration

All text content is configurable via `config.yaml`:

### Branding (`branding`)
- `intro_text` - Intro paragraph
- `intro_text2` - Second intro line
- `source_link_text` - Source code link text
- `source_link_url` - Source code link URL
- `show_powered_by` - Show "powered by" footer
- `powered_by_text` / `powered_by_url` - Powered-by link

### Site Profile (`profile`)
- `avatar` - Avatar image URL
- `bio` - Short bio text
- `links` - List of links with `name` and `url`

### Site Identity (`site`)
- `title` - Site title
- `author` - Author display name
- `url` - Canonical HTTPS origin
- `description` - Site description
- `language` - Language code
- `navigation.items` - Navigation links with `name` and `url`

## Variable Substitution

In about page content, you can use these variables:
- `{{ author_name }}` - Blog author's name
- `{{ github_name }}` - GitHub username
- `{{ blog_url }}` - Blog URL

## File Structure

```
Escape1/
├── base.html          # Base template with navigation
├── home.html          # Homepage (uses branding config)
├── index.html         # Blog post list (uses pagination)
├── post.html          # Individual post
├── about.html         # About page (uses profile config)
├── tags.html          # Tag index
├── tag.html           # Single tag page
└── static/
    ├── css/style.css  # Main stylesheet
    ├── js/theme.js    # Dark mode toggle
    └── images/favicon.png
```

## Design

- Single column layout, max-width 680px
- Warm white background (#faf9f6) in light mode
- System font stack for fast loading
- 17px font size with 1.7 line height
- Blue links with hover effects

## Credits

Inspired by:
- [Hugo Bear Blog](https://janraasch.github.io/hugo-bearblog/)
- [Armin Ronacher's Blog](https://lucumr.pocoo.org/)
