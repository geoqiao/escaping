# BearMinimal Theme

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
2. Set your theme path in config.yaml:
   ```yaml
   theme:
     path: "templates/BearMinimal"
     seo: "templates/seo"
   ```
3. Run the generator:
   ```bash
   uv run blog-gen <TOKEN> <REPO>
   ```

## Configuration

All text content is configurable via `config.yaml`:

### Home Page (`home`)
- `intro_line1` - First intro paragraph
- `intro_line2` - Second intro paragraph
- `source_code_text` - Source code link text
- `source_code_url` - Source code link URL
- `recent_posts_title` - Recent posts section title
- `view_all_text` - "View all" link text
- `post_count` - Number of posts to show on home page

### About Page (`about`)
- `page_title` - Page title
- `sections` - Array of sections with `title`, `type`, and `content`
  - `type: paragraphs` - Multiple paragraphs
  - `type: list` - Bullet list
  - `type: contact` - Contact links

### Navigation (`navigation`)
- `items` - Array of navigation links with `name` and `url`

### Pagination (`pagination`)
- `prev_text` - Previous page button text
- `next_text` - Next page button text

### Tags Page (`tags`)
- `page_title` - Page title

## Variable Substitution

In about page content, you can use these variables:
- `{{ author_name }}` - Blog author's name
- `{{ github_name }}` - GitHub username
- `{{ blog_url }}` - Blog URL

## File Structure

```
BearMinimal/
├── base.html          # Base template with navigation
├── home.html          # Homepage (uses home config)
├── index.html         # Blog post list (uses pagination_config)
├── post.html          # Individual post
├── about.html         # About page (uses about config)
├── tags.html          # Tag index (uses tags_config)
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
