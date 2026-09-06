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
  → staged output publication
```

`Settings` is explicitly injected into compilation and `SiteBuilder`. Rendering and artifact
validation consume `SiteModel`; they do not read Config again. `SiteMetadata` is the sole source
for site identity, profile, navigation, comments, branding, SEO verification, and Theme asset
metadata. The CLI first resolves strict Config overrides with optional trusted
repository/Pages context and public Profile inputs; see [site inputs](site-inputs.md).
Model construction and rendering never fetch Profile data.

## Content and routes

Published Issues follow [`issue-content-v1.md`](contracts/issue-content-v1.md). Blog content
defaults `slug` to the Issue number; an explicit lower-case kebab-case override
is preserved. Idea and About reject slugs. An explicit About selection must be
valid; otherwise the sole valid published About is discovered, with Profile About
when none exists. Multiple candidates fail. Optional YAML is safely parsed and
removed before Markdown rendering; generated HTML is sanitized before entering
the model.

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

Quiet is the default; geoqiao.me, Escape1 and Escape2 are alternatives. The default
menu is Home, Blog, Ideas, Projects, Tags, About, RSS. Explicit
`site.navigation.items` replaces it entirely, preserving names/order, allowing
removal of Home or `[]`, independently of the brand's Home link. No product page
is removed by hiding a menu entry.

Comments default off. Set `comments.enabled: true` and separately authorize the
[Utterances GitHub App](https://github.com/apps/utterances) for the public repository;
visitors also authorize OAuth to write through the widget. Configuration alone
does not install the App or prove posting works. Disabled pages have no comment
script, iframe, loading state or dead Discuss link. Profile About never has comments.

Templates and static assets use **Theme API 2**, Jinja `StrictUndefined` and
autoescape. API 1 is rejected with an explicit migration error and old output
preserved, not silently adapted. The [Theme authoring guide](themes/authoring.md)
defines all files, page-scoped context, JSON-LD identity, assets, keyboard behavior
and [migration](themes/authoring.md#migrating-from-api-1). There is no remote Theme
fetch, inheritance between Themes or cache/update system.

Site Thesis and Site Profile copy remain in `SiteMetadata` for compatible local
Themes, but presentation is Theme-specific. Escape2 renders configured thesis
lines; `geoqiao.me` keeps profile bio out of Home and Issue About. All four Themes
render Profile About without a source Issue, date, or comments. Local templates
must branch on `about_is_profile` before accessing Issue-only fields; see the
[About migration](site-inputs.md#about-and-local-themes).

The generator-owned `src/escaping/static/comments.js` is copied into the selected Theme's
output asset directory. Theme `_comments.html` files declare only the container, safe data
attributes, and light/dark default. The shared script preserves Issue-number binding, Utterances
origin/source checks, `postMessage` + `MutationObserver` theme following, failure fallback, and
the Safari workaround that removes injected iframe `loading="lazy"`.

## Output safety

Output paths are contained beneath the Config directory. A build writes to a registered staging
directory, validates all expected routes, metadata, links, resources, XML, sitemap, and robots,
and only then publishes it with portable directory renames. Failures before publication preserve
the previous output. A successful replacement of existing local output may have a brief path
window while the old tree is held in a uniquely owned backup; promotion failure restores that
backup, and rollback failure preserves both recovery trees with explicit path diagnostics.

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
