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

Blog slugs default to the Issue number, with optional front matter overrides;
they are never derived from titles. Idea tags are display-only. About uses an
explicit immutable Issue number, otherwise the sole valid published About Issue,
otherwise Profile About without a fabricated Issue or discussion. Front matter
is stripped before Markdown rendering; HTML goes through the allowlist sanitizer.

## Start a site

Use **Use this template** at [escaping-template](https://github.com/geoqiao/escaping-template).
No local Python, PAT, or manually created publishing labels are required.

> **Public preview:** an existing production site's build and deployment have been verified;
> first-time template creation and the complete new-user initialization flow have not.

1. Create `username.github.io` (public for GitHub Free), keep Issues/Actions enabled, and select **GitHub Actions** in **Settings → Pages**.
2. Save an Issue with a title and Markdown body; wait for label preparation, then refresh the label selector.
3. Add one of `type:blog`, `type:idea`, or `type:about`, plus `published` when ready, and check the Actions deployment.

Project-site subpaths are unsupported; an existing custom domain must serve an HTTPS root URL.
See the [starter instructions](starter/README.md).

## Local development

Requires Python 3.14.x, [`uv`](https://docs.astral.sh/uv/), and a GitHub token that can read the target repository's Issues.

```bash
uv sync
export GITHUB_TOKEN=...
uv run escpe --config /path/to/site/config.yaml
# Serve the site Config-relative output as the document root.
uv run python -m http.server 8000 --directory /path/to/site/output
```

`security.token_env` selects the token environment variable dynamically (default
name: `GITHUB_TOKEN`). The generator ships `config.example.yaml` as an expanded
reference. Without context, provide an actual `github.repo` and HTTPS root
`site.url`; Organization owners also require explicit `allowed_authors`.
Alternatively, a verified non-secret `--context context.json` supplies repository
and Pages identity so Config can be `{}`. Missing identity fields use the public
owner profile, never the workflow actor. Projects need only a selected
`repository`; explicit title/summary override public enrichment.

See [site input sources and boundaries](docs/site-inputs.md), including the
Site Orchestrator interface for safely reading the token variable name. The
default Theme is **Quiet**, with Home, Blog, Ideas, Projects, Tags, About and RSS
as the default menu. An explicit `site.navigation.items` list replaces it entirely,
including order, names, removal of Home or `[]`; the brand links Home independently.
Comments default off: set `comments.enabled: true` and separately authorize the
[Utterances App](https://github.com/apps/utterances). Profile About never has comments.
The canonical origin is owned by `site.url` in the site repository's Site Config,
not by a Theme or by the generator. [Quiet](docs/themes/quiet.md) is the only
built-in Theme, using neutral black/white surfaces with restrained avatar-magenta
accents. Independently maintained local Themes use the same public contract.
The production workflow is owned by the site repository; see the
[site Pages workflow](https://github.com/geoqiao/geoqiao.github.io/blob/main/.github/workflows/pages.yml).
Any consumer workflow must pin the compiler to a reviewed release or full 40-character SHA.

## Custom Themes — API 2

The [Theme authoring guide](docs/themes/authoring.md) documents the complete manifest,
per-page context, static/shared assets, keyboard requirements and diagnostics.
API 1 is rejected, not adapted. Follow the [migration checklist](docs/themes/authoring.md#migrating-from-api-1)
for IdeaTag, About variants, optional comments, manifest and explicit old-site
Config; changing only the version string is insufficient.

`geoqiao.me`, `Escape1`, and `Escape2` are no longer shipped. Explicit selections
fail without replacing old output or silently falling back to Quiet. Before
upgrading, select Quiet or preserve the old design as a site-owned local Theme;
see [removed-theme migration](docs/themes/authoring.md#migrating-removed-built-in-themes).
Theme API 2, `capabilities`, and the optional `site.thesis` presentation hint
remain supported. Structured data, Profile About and safe rendering rules have
one source of truth: the Theme authoring guide.

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
