# Strict Site Compiler guide

## Build boundary

`escaping` has one production path:

```text
IssueSnapshot[] + Settings + Project Catalog
  → ContentCompiler
  → SiteBuilder(RouteRegistry)
  → SiteModel(SiteMetadata + pages + Routes)
  → RenderService(LoadedTheme)
  → SiteArtifactValidator
  → atomic output publication
```

`Settings` is explicitly injected into compilation and `SiteBuilder`. Rendering and artifact
validation consume `SiteModel`; they do not read Config again. `SiteMetadata` is the sole source
for site identity, profile, navigation, comments, branding, SEO verification, and Theme asset
metadata.

## Content and routes

Published Issues follow [`issue-content-v1.md`](contracts/issue-content-v1.md). Blog content
requires a lower-case kebab-case `slug`; Idea and About reject slugs. The configured About Issue
is a singleton. YAML is safely parsed and removed before Markdown rendering; generated HTML is
sanitized before entering the model.

`RouteRegistry` constructs the only `Route` model. Every page stores its complete registered
Route, including canonical path, output path, and canonical URL. It also rejects path/output
collisions and supplies Atom, sitemap, robots, and internal-link mappings.

Directory routes write `index.html`:

- `/`, `/blog/`, `/blog/{slug}/`
- `/ideas/`, `/ideas/{issue_number}/`
- `/about/`, `/projects/`
- `/tags/`, `/tags/{tag}/`
- `/atom.xml`, `/sitemap.xml`, `/robots.txt`

## Themes and comments

`ThemeLoader` loads one declaration:

- `source: builtin`: a package resource from `src/escaping/themes/`;
- `source: local`: a directory relative to the Config file.

`geoqiao.me` is the Chinese-first default built-in Theme; Escape1 and Escape2 are
alternative reference Themes. Templates and static assets come from the same
validated manifest and use Jinja `StrictUndefined` with autoescape. Theme
fetching and commit pinning are orchestration concerns, not compiler behavior.

The generator-owned `src/escaping/static/comments.js` is copied into the selected Theme's
output asset directory. Theme `_comments.html` files declare only the container, safe data
attributes, and light/dark default. The shared script preserves Issue-number binding, Utterances
origin/source checks, `postMessage` + `MutationObserver` theme following, failure fallback, and
the Safari workaround that removes injected iframe `loading="lazy"`.

## Output safety

Output paths are contained beneath the Config directory. A build writes to a registered staging
directory, validates all expected routes, metadata, links, resources, XML, sitemap, and robots,
and only then atomically replaces the old output. Failed builds preserve the previous site.

## Commands

```bash
uv sync
export GITHUB_TOKEN=...
uv run escpe --config /path/to/site/config.yaml
uv run python -m http.server 8000 --directory /path/to/site/output
uv run pytest -q
uv run ruff check src/escaping tests
uv run ruff format --check src/escaping tests
uv run ty check
```

The HTTP document root must be `output/`; `/output/` is not a site URL prefix.
