# 04 — Compile a strict Blog detail tracer

**What to build:** Compile a published Blog Issue through the new snapshot, content validation, internal model, safe Markdown, route, and both existing themes to a canonical detail page.

**Blocked by:** 01 — Expand the Issue ingestion seam; 02 — Enforce strict configuration and output containment.

**Status:** ready-for-agent

- [x] Blog selection obeys PR exclusion, allowed-author comparison, the `published` gate, and exactly one supported `type:*` label; unauthorized authors warn and unpublished Issues are ignored without body parsing.
- [x] The complete accepted Issue Content Contract governs front matter envelope, safe YAML, UTF-8 size, unknown and duplicate fields, normalization, slug, description, date, title, and non-empty body validation.
- [x] Front matter is removed before Markdown conversion and none of its fields appears in rendered body HTML.
- [x] Markdown supports the documented GFM-compatible subset and allowlist sanitization preserves ordinary content and pasted GitHub images while removing dangerous elements, attributes, and URL schemes.
- [x] The resulting Blog model contains authored `created_date`, GitHub publication and update timestamps, canonical route, description, tags, body HTML, and immutable Issue number for comments.
- [x] The detail route is `/blog/{slug}/`, maps to a directory index output, and is not derived from the title.
- [x] Escape1 and Escape2 render the new Blog model without PyGithub objects, label interpretation, YAML parsing, or an auxiliary slug map.
- [x] All detectable errors from multiple published Blog fixtures are returned together with stable diagnostic fields; any error blocks rendering.

## Comments

Implemented test-first and approved after independent review. Validation: 528 tests passed; changed-tree Ruff/format, full ty, and diff checks passed. The strict Blog detail path remains an isolated tracer until the later production cutover ticket; the legacy default build remains internally consistent.
