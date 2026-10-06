# Themes

Themes you can use with one line in `config.yaml`. Each one lives in its
author's GitHub repository; this page only links to them. To use one, copy its
`theme.use` line and read its README for options and the `pages` settings it
needs. See [Using a Theme from GitHub](authoring.md#using-a-theme-from-github).

Quiet is built in and needs no line at all; see [Quiet](quiet.md).

## From [geoqiao/escaping-themes](https://github.com/geoqiao/escaping-themes)

### Escape1

```yaml
theme:
  use: github.com/geoqiao/escaping-themes/escape1@v1.0.0
```

A minimal reading column on a warm off-white page, with dark mode and code
highlighting. Every page kind. Formerly built into escaping.

![Escape1](https://raw.githubusercontent.com/geoqiao/escaping-themes/v1.0.0/escape1/screenshot.png)

### Escape2

```yaml
theme:
  use: github.com/geoqiao/escaping-themes/escape2@v1.0.0
```

A dark, Nord-coloured terminal look with a `user@escaping ~ $` prompt and
monospace headings. Every page kind. Formerly built into escaping.

![Escape2](https://raw.githubusercontent.com/geoqiao/escaping-themes/v1.0.0/escape2/screenshot.png)

### geoqiao.me

```yaml
theme:
  use: github.com/geoqiao/escaping-themes/geoqiao-me@v1.0.0
```

A Chinese-first writer's site with editorial index rows, a 720px reading
column and a section outline. Chinese and English interface. Every page kind.
Formerly built into escaping.

![geoqiao.me](https://raw.githubusercontent.com/geoqiao/escaping-themes/v1.0.0/geoqiao-me/screenshot.png)

### Paper

```yaml
theme:
  use: github.com/geoqiao/escaping-themes/paper@v1.0.0
pages:
  tags: false
  projects: false
```

A small notebook: warm paper colours, serif text, no JavaScript.

![Paper](https://raw.githubusercontent.com/geoqiao/escaping-themes/v1.0.0/paper/screenshot.png)

### Ledger

```yaml
theme:
  use: github.com/geoqiao/escaping-themes/ledger@v1.0.0
```

A field-journal look with ruled sections, in English and Chinese. Every page
kind, plus templates for a `/now/` page and one page per project.

![Ledger](https://raw.githubusercontent.com/geoqiao/escaping-themes/v1.0.0/ledger/screenshot.png)

### Quiet Notes

```yaml
theme:
  use: github.com/geoqiao/escaping-themes/quiet-notes@v1.0.0
```

Quiet with its own Home introduction, stylesheet and display font, and a
`/now/` page.

![Quiet Notes](https://raw.githubusercontent.com/geoqiao/escaping-themes/v1.0.0/quiet-notes/screenshot.png)

## Adding your Theme

Put the Theme in a public GitHub repository (one repository can hold several,
one per folder), tag a version, and open a pull request that adds a section
here with:

- the name, as a heading;
- the `theme.use` line with a tag or commit, plus any `pages` settings the
  Theme needs;
- one or two sentences on how it looks and which pages it has;
- a screenshot at that same version.

Before you open it, run `escaping-site theme check` on the Theme at the root of a host
and under a path (see [Sharing a Theme](authoring.md#sharing-a-theme)).
Listing a Theme here does not mean escaping has reviewed its code; read a
Theme before you use it (see [Security](authoring.md#security)).
