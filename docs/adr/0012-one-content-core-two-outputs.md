---
status: superseded by ADR-0013
amends: ADR-0011 (the export ran the Site Compiler's content step and read the full Site Config)
---

# One content core, two outputs

ADR-0011 added the export as a branch of the build: it registered the site's
routes, validated the whole Site Config and loaded the Theme code, only to
write Markdown. A site built with another tool had to fill in `site.title`,
could not keep its own settings in `config.yaml`, and lost its Ideas when
`pages.ideas` was false, a switch for pages it does not have.

`escaping` keeps both products: a finished site for GitHub Pages, and the
content alone for a site built elsewhere.

## Decision

**Issue Content is compiled by a core that knows no site.** `issue_content`
selects Issues, applies the content rules and resolves every value. It knows no
URL, page switch or Theme. `escaping-site build` adds addresses and page HTML to
its entries; `escaping-site export` writes them as files. Neither output imports
the other, and a test keeps the export from loading the site's modules.

**The Config is split by owner.** `github`, `about` and `security` decide
which Issues are published, and both outputs read them. Every other section
belongs to the build. The export checks only the three and ignores the rest,
unknown sections included.

**Rules about a site left Issue Content v1.** Rendering and route integrity are
now Site Build v1 (removed in 0.6.0). Issue Content v1 keeps what
is true for both outputs, including that a body must render and sanitize.

**Theme API 4 is frozen.** It serves the built site and gains no features. A
site that needs more than a Theme can do takes the export.

## Consequences

The export publishes every content type and never refuses a slug for colliding
with a page of a built site; `PAGE_OFF` and `ROUTE_COLLISION` are the build's.
A build and an export agree on which Issues are published whenever the build
has every section on.

A mistyped top-level section is not reported by the export, because any
unknown section may be the consuming site's.

Bodies are still rendered and sanitized during an export, to judge them and to
derive the default description. A build under a sub-path renders them a second
time for its links.

Extra pages and Projects have no site of the author's own using them once that
site takes the export; only tests keep them working.
