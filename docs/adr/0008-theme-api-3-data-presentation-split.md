---
status: superseded by ADR-0013
supersedes: Theme API 2 (ADR-0007 keeps Quiet as the only built-in Theme)
---

# Theme API 3: the compiler owns data, Themes own presentation

Theme API 2 let the compiler decide which pages exist, which variables every
template receives and which SEO tags each page must emit, then re-checked every
Theme's HTML on each build. Themes could not add a page, declare their own
settings or change one file of Quiet without copying all of it. Quiet-only
choices (tagline, featured posts, footer branding, Utterances colours) lived in
the shared Site Config. The geoqiao.me Theme needed project detail pages and
therefore re-implemented the build in a 270-line site script.

## Decision

The compiler turns Issues and the Site Config into data, guarantees routes and
publishes safely. A Theme turns that data into pages. Quiet is an ordinary
Theme that happens to ship with the package.

**Site Config has two layers.** A value belongs to the site layer when it still
means something after switching Themes (title, origin, author, language,
navigation, profile, projects, comment repository, SEO verification); otherwise
it is a Theme option. The Theme is selected with
`theme: {use: quiet | ./relative/path, options: {...}}`; options are validated
against the selected Theme's schema, with unknown names reported with a
suggestion.

**theme.yaml API 3** declares `api: 3`, an optional `extends` (a built-in
Theme name), typed `options` with defaults, extra `pages` (static paths or
`for_each: projects`) and UI `strings` per language. A Theme with
`extends: quiet` overrides individual templates and static files; everything it
does not provide comes from Quiet. Customisation therefore has three steps:
options in `config.yaml`, a two-line Theme that overrides single files, or a
complete Theme.

**Templates receive four names:** `site`, `page`, `theme` (resolved options)
and `t` (strings for the site language). Theme static files are published at
`/assets/`; compiler-owned scripts (comments, Mermaid) at `/assets/escaping/`.

**Build-time checks cover integrity, not style.** Every build still checks
that each route has an output, that internal links and assets resolve and that
output stays inside its owned directory. Canonical/Open Graph conformance
moves to the offline `escaping-site theme check`, which renders a Theme against
synthetic content.

**One bad Issue skips that Issue.** Content errors in a Blog or Idea Issue
exclude that Issue, are reported with the Issue number and make the CLI exit
with status 2 after publishing. Config, Theme, About-selection and site-wide
route errors still stop the build before publication.

**Tag names and tag routes are separate.** The label text is the display name;
the route key is its normalised form and may contain Unicode letters.

**Deployment uses a reusable Action** pinned by the site repository; the Action
reports diagnostics in the job summary and as annotations.

## Consequences

Theme API 2 manifests, `theme_path`, the flat template variables,
`site.featured_posts`, `site.thesis`, `profile.tagline` and `branding` are
removed without a compatibility layer; the release notes carry the migration.
The compiler no longer protects Themes from their own SEO mistakes during a
build, and a skipped Issue disappears from the site until fixed. In exchange a
Theme can add pages and options without compiler changes, a site can adjust
Quiet without forking it, and one malformed Issue no longer freezes the site.
Output publication, HTML sanitisation, route uniqueness and the no-network
Theme loader are unchanged.
