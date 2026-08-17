# escaping

`escaping` is a strict static Site Compiler whose content source is GitHub
Issues. It compiles conforming Issue snapshots from
`docs/contracts/issue-content-v1.md` into one `SiteModel`. A single
`RouteRegistry` owns page routes, output paths, canonical URLs, Atom, sitemap,
robots, and internal links. The complete artifact is validated before portable
staged publication using directory renames with rollback.

## v1 routes

| Content | canonical route |
| --- | --- |
| Home | `/` |
| Blog archive/detail | `/blog/`, `/blog/{slug}/` |
| Ideas | `/ideas/`, `/ideas/{issue_number}/` |
| About | `/about/` |
| Projects | `/projects/` |
| Tags | `/tags/`, `/tags/{tag}/` |
| Atom / sitemap / robots | `/atom.xml`, `/sitemap.xml`, `/robots.txt` |

Blog slugs come from Issue front matter and are never derived from titles. Idea
tags are display-only; About is selected by its immutable configured Issue
number. Front matter is stripped before Markdown rendering, and the resulting
HTML goes through the allowlist sanitizer.

## Local development

```bash
uv sync
export GITHUB_TOKEN=ghp_xxx
uv run escpe --config /path/to/site/config.yaml
# Serve the site Config-relative output as the document root.
uv run python -m http.server 8000 --directory /path/to/site/output
```

`security.token_env` selects the token environment variable dynamically. The
generator ships `config.example.yaml`, and the default Theme is `geoqiao.me`.
The canonical origin is owned by `site.url` in the site repository's Site Config,
not by a Theme or by the generator. Escape1, Escape2, and geoqiao.me share the
same template contract, comments behavior, and RouteRegistry rules.
The production workflow is owned by the site repository; see the
[site Pages workflow](https://github.com/geoqiao/geoqiao.github.io/blob/main/.github/workflows/pages.yml).
Any consumer workflow must pin the compiler to a reviewed release or full 40-character SHA.

## Canonical origin and URL migration boundaries

The production site repository owns `config.yaml`; its current `site.url` is
`https://geoqiao.me/`. The compiler derives canonical, Open Graph, Atom, sitemap,
and robots URLs from the Config supplied at build time, so the generator does not
silently impose geoqiao.me on another consumer.

Two historical-URL cases are deliberately separate:

- **Legacy `.html` Blog URLs:** the compiler does not generate
  `/blog/{slug}.html` aliases or redirects. This remains the decision in
  [ADR-0003](docs/adr/0003-drop-legacy-html-urls.md).
- **Pinyin slug migrations:** the site repository may keep an explicit mapping such
  as `/blog/old-pinyin-slug/` → `/blog/new-english-slug/` and run its own
  `render_slug_redirects.py` after compilation. This is not title-derived slug
  generation and does not reopen `.html` compatibility; see
  [ADR-0005](docs/adr/0005-site-owned-blog-slug-migration-redirects.md).

## Verification

```bash
uv run pytest -q
uv run ruff check src/escaping tests
uv run ruff format --check src/escaping tests
uv run ty check
git diff --check
```

After generation, inspect Home, Blog, Ideas, About, Projects, Tags, Atom,
sitemap, and robots. Serve `output/` as the document root rather than opening
`/output/`; otherwise root routes such as `/blog/` and `/ideas/` return 404.
Historical `.html` Blog URLs have no aliases or redirects in the compiler. Any
explicit non-`.html` slug migration redirect is a site-owned post-processing step;
see [ADR-0003](docs/adr/0003-drop-legacy-html-urls.md) and
[ADR-0005](docs/adr/0005-site-owned-blog-slug-migration-redirects.md).
