# 05 — Deliver the paginated Blog archive

**What to build:** Give visitors a deterministic, paginated Blog archive generated from validated Blog models in both existing themes.

**Blocked by:** 04 — Compile a strict Blog detail tracer.

**Status:** ready-for-agent

- [x] Blog entries sort by Issue `created_at` descending, with Issue number descending as the tie-breaker.
- [x] Page one uses `/blog/`; pages starting at two use `/blog/page/{number}/` with stable trailing-slash output paths.
- [x] The configured positive page size is honored and defaults to 10.
- [x] Archive navigation, detail links, and canonical links come from registered routes rather than template string concatenation.
- [x] An empty Blog collection still produces a valid, intentional archive page.
- [x] Escape1 and Escape2 render equivalent archive behavior using internal models only.
- [x] Pagination tests cover boundaries, ties, canonical routes, and empty input.

## Comments

Implemented test-first and approved after independent review. Validation: 547 tests passed; changed-tree Ruff/format, full ty, and diff checks passed. The strict archive remains an isolated tracer; the legacy default build is adapted to the same internal template model without changing its `.html` artifacts.
