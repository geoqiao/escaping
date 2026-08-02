# 07 — Deliver Blog Tags

**What to build:** Let visitors browse the Blog taxonomy through a Tags index and per-tag archives derived only from published Blog content.

**Blocked by:** 04 — Compile a strict Blog detail tracer.

**Status:** ready-for-agent

- [x] Only normalized `tag:*` labels from valid published Blog Issues enter the public taxonomy.
- [x] The Tags index uses `/tags/` and each tag archive uses `/tags/{tag}/`, with registered canonical and output paths.
- [x] Tag uniqueness and comparisons follow the accepted NFC and case-insensitive rules while preserving a deterministic display value.
- [x] Tag pages link to canonical Blog routes and never construct `.html` URLs.
- [x] Empty Blog tags still produce an intentional `/tags/` empty state without spurious archives.
- [x] Escape1 and Escape2 render equivalent Tags pages from internal Tag and Blog models.
- [x] Tests cover normalization, duplicate labels, ordering, empty input, and route collisions.

## Comments

Implemented test-first and approved after independent review. Validation: 691 tests passed; changed-tree Ruff/format, full ty, and diff checks passed. The strict taxonomy remains an isolated tracer, with legacy adapters preserving existing `.html` artifacts until cutover.
