# Site Build Contract v1

Status: **Accepted**

## 1. Purpose and scope

This contract defines what `escaping-site build` adds to accepted
[Issue Content](issue-content-v1.md) to make a site: how a body becomes HTML
and how every page gets one address. It was sections 9 and 11 of Issue Content
v1 until the [Content Export](content-export-v1.md) gave the same content a
second output.

It does not apply to `escaping-site export`. A site built with another tool
owns its rendering, its safety and its routes.

The key words **MUST**, **MUST NOT**, **SHOULD** and **MAY** are normative
requirements.

## 2. Rendering and security

- Markdown MUST be rendered as GitHub-Flavored Markdown or a documented,
  compatible subset.
- Raw HTML MUST be sanitized with an allowlist after Markdown rendering.
- A task list item shows its state as text: `- [x]` renders as ☑ and
  `- [ ]` as ☐, because the sanitizer removes `<input>`.
- Scripts, event-handler attributes, dangerous URL schemes, and unsafe embeds
  MUST be removed or rejected.
- Jinja/template autoescape does not replace Markdown sanitization.
- Front matter MUST NOT enable arbitrary template selection, code execution,
  script injection, or per-content plugins in v1.

## 3. Route integrity

The compiler MUST build one global route registry before writing output and
reject:

- duplicate canonical paths;
- duplicate slugs;
- malformed tag keys;
- reserved-route collisions.

Blog tags use `/tags/` for the index and `/tags/{tag}/` for tag archives.
HTML page routes MUST end with `/`. Blog slugs are lower-case ASCII; tag keys
are Unicode letters and digits (NFC, case-folded) joined by hyphens.
The machine-readable endpoints are `/atom.xml`, `/sitemap.xml`, and `/robots.txt`,
without a trailing slash; they belong to the same route registry.
Canonical paths MUST be converted to Unicode NFC before validation. Collision
checks MUST additionally compare case-folded paths so local case-insensitive
filesystems and GitHub Pages cannot produce divergent output.
The complete reserved-route set comes from all pages registered for the site,
not from a separate hard-coded Issue list.

Canonical links, internal links, sitemap entries, feed URLs, Open Graph URLs,
and output filesystem paths MUST be produced from that same route registry.
Every validation error SHOULD include a stable error code and Issue number when
an Issue caused the error. The compiler MUST collect and report all detectable
content validation errors in one run. A Blog or Idea Issue with its own content
error is skipped and reported, and the rest of the site is still published (the
CLI exits with status 2). Errors in Config, the Theme, the About Issue that
`about.issue_number` selects, or site-wide routes fail the build and publish
nothing.

A section the Config turns off publishes nothing: an Idea Issue with
`pages.ideas: false`, or an About Issue with `pages.about: false`, is left out
with a warning (`PAGE_OFF`).
