# escaping

`escaping` is a strict static Site Compiler whose content source is GitHub
Issues. It compiles conforming Issue snapshots from
`docs/contracts/issue-content-v1.md` into one `SiteModel`. A single
`RouteRegistry` owns page routes, output paths, canonical URLs, Atom, sitemap,
robots, and internal links. The complete artifact is validated before atomic
publication.

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
uv run escpe
# Run from the repository root; serve output as the document root.
uv run python -m http.server 8000 --directory output
```

`security.token_env` selects the token environment variable dynamically. Strict
builds require `theme_lock`. The default `config.yaml` uses `geoqiao.me`, an
Escape2-based terminal visual baseline. Escape1, Escape2, and geoqiao.me share
the same template contract, comments behavior, canonical origin
`https://geoqiao.me`, and RouteRegistry rules.

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
Historical `.html` Blog URLs have no aliases or redirects;
see `docs/adr/0003-drop-legacy-html-urls.md`.
