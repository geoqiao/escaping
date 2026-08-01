# 05 — Deliver the paginated Blog archive

**What to build:** Give visitors a deterministic, paginated Blog archive generated from validated Blog models in both existing themes.

**Blocked by:** 04 — Compile a strict Blog detail tracer.

**Status:** ready-for-agent

- [ ] Blog entries sort by Issue `created_at` descending, with Issue number descending as the tie-breaker.
- [ ] Page one uses `/blog/`; pages starting at two use `/blog/page/{number}/` with stable trailing-slash output paths.
- [ ] The configured positive page size is honored and defaults to 10.
- [ ] Archive navigation, detail links, and canonical links come from registered routes rather than template string concatenation.
- [ ] An empty Blog collection still produces a valid, intentional archive page.
- [ ] Escape1 and Escape2 render equivalent archive behavior using internal models only.
- [ ] Pagination tests cover boundaries, ties, canonical routes, and empty input.
