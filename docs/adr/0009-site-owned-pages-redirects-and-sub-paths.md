---
status: superseded by ADR-0013
supersedes: the Theme `pages` of ADR-0008, ADR-0003 and ADR-0005
---

# Theme API 4: the site decides its pages; Themes supply templates

Under Theme API 3, escaping fixed the nine page kinds, a Theme had to ship a
template for each of them and could declare extra pages in `theme.yaml`. A
site could not turn a page off or move it, a small Theme had to fill templates
it did not want, and the pages of a site changed when it switched Themes. Old
addresses needed a site script, and a GitHub project site under a path could
not be built at all.

## Decision

**Three owners.** escaping owns the page kinds, the template name for each kind
and every address. The site's `config.yaml` owns which pages exist and where
(`pages`), and which old addresses redirect (`redirects`). The Theme owns only
templates and static files.

**Template fallback.** A Theme needs `blog.html` and `post.html`. Home, Ideas
and a tag page fall back to `blog.html`; an Idea and About fall back to
`post.html`. `tags.html` and `projects.html` have no fallback, because their
items differ; when such a page is on and the Theme lacks the template, the build
stops before reading Issues and names both fixes (add the template, or turn the
page off). No page is skipped silently.

**One page shape.** Every page has `item`, `items`, `pagination`, `newer`,
`older`, `tag` and `project`, `none` when unused, and posts, Ideas and About
share the fields a single page shows. That is what makes the fallback work.

**Built-in redirects.** `redirects` maps old site paths (ending in `/` or
`.html`) to pages. Each becomes a static page with a refresh and a canonical
link. A page always wins over a redirect; a redirect to a missing page is left
out with a warning, because pages come from Issues that may be unpublished.

**Sites under a path.** `site.url` may carry a path. Routes, Issue links and
root-relative Config values include it; Themes pass their own addresses through
the `url` filter, and the output check names that filter when an address leaves
the site. `robots.txt` is written only at the root of a host.

## Consequences

API 3 Themes are rejected with a link to the migration notes; `pages` in
`theme.yaml` is rejected with its new place. `site.routes.<name>`,
`site.about` and a Blog tag's `path` can now be `none`, so Themes must guard
links to optional pages. ADR-0003's refusal of `.html` aliases and ADR-0005's
site-owned redirect scripts give way to `redirects`, which stays explicit: no
redirect is inferred from titles or slug history.
