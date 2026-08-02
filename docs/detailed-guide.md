# Strict Site Compiler guide

This repository now uses one build path:

```text
GitHub Issue snapshots
  -> ContentCompiler
  -> ProjectCompiler
  -> SiteModelBuilder + RouteRegistry
  -> RenderService
  -> SiteArtifactValidator
  -> OutputStagingService
  -> output/
```

## Content contract

Issue selection and validation follow `docs/contracts/issue-content-v1.md`.
Published content has exactly one supported `type:*` label. Blog content
requires an explicit lower-case kebab-case `slug`; Idea and About content do
not accept a slug. The configured About Issue is a singleton. YAML is safely
parsed, removed from the body, and rendered HTML is sanitized before it enters
the model.

## Routes and artifacts

`RouteRegistry` owns all public routes and maps trailing-slash pages to
`index.html` directories:

- `/`, `/blog/`, `/blog/{slug}/`
- `/ideas/`, `/ideas/{issue_number}/`
- `/about/`, `/projects/`
- `/tags/`, `/tags/{tag}/`
- `/atom.xml`, `/sitemap.xml`, `/robots.txt`

The same registry supplies canonical URLs, internal model links, Atom entries,
sitemap membership, robots, Open Graph/Twitter URLs, and JSON-LD page URLs. The
artifact validator rejects missing/unregistered files, broken internal links,
front matter leakage, invalid XML, and origin mismatches.

## Themes and comments

`ThemeResolver` accepts a full-SHA `theme_lock`, validates `theme.yaml`, and
loads site overrides before the locked declarative theme with Jinja
`StrictUndefined`. `Escape1`, `Escape2`, and `geoqiao.me` use the same content
contract. The geoqiao.me theme follows the approved Escape2 visual baseline;
see `docs/themes/geoqiao-me-v1-baseline.md`.

The shared Utterances include binds comments by immutable Issue number, follows
`comments.theme_mode: auto` with `postMessage` and `MutationObserver`, and keeps
the Safari workaround that removes lazy loading from injected iframes.

## Local commands

```bash
uv sync
export G_T=ghp_xxx
uv run blog-gen
# Run from the repository root; serve generated output as the document root.
uv run python -m http.server 8000 --directory output
uv run pytest -q
uv run ruff check src/github_blog tests
uv run ruff format --check src/github_blog tests
uv run ty check
```

Build output is staged and published only after full validation. For local
smoke tests, map `output/` to the HTTP document root; do not browse through an
`/output/` URL, or root routes such as `/blog/` will not resolve. Unsafe output
roots and failed builds preserve the previous output tree. Historical `.html`
Blog routes are intentionally not generated, aliased, or redirected.
