# Escape2 Theme

A dark, terminal-inspired blog theme for github-blog. Inspired by the [Nightfall](https://github.com/LordMathis/hugo-theme-nightfall) Hugo theme.

## Aesthetic

- Retro-futuristic terminal vibe
- Deep dark backgrounds with cool blue accent (`#80AADD`)
- JetBrains Mono for headers and code
- Source Sans 3 for body text
- Blinking terminal cursor in the logo
- Post cards with glowing left border on hover
- Dark mode only

## Templates

- `base.html` — Layout with terminal-style header
- `home.html` — Landing page with avatar, bio, and recent posts
- `index.html` — Paginated blog post list
- `post.html` — Single article with Utterances comments
- `tag.html` — Posts filtered by tag
- `tags.html` — All tags list
- `about.html` — About page

## Files

```
templates/Escape2/
├── base.html
├── home.html
├── index.html
├── post.html
├── tag.html
├── tags.html
├── about.html
├── README.md
└── static/
    ├── css/
    │   ├── style.css
    │   └── prism-dracula.css
    ├── js/
    │   └── prism.js
    └── images/
        └── favicon.png
```

## Usage

Set in `config.yaml`:

```yaml
theme:
  name: Escape2
```
