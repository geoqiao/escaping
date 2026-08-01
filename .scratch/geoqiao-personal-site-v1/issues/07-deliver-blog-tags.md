# 07 — Deliver Blog Tags

**What to build:** Let visitors browse the Blog taxonomy through a Tags index and per-tag archives derived only from published Blog content.

**Blocked by:** 04 — Compile a strict Blog detail tracer.

**Status:** ready-for-agent

- [ ] Only normalized `tag:*` labels from valid published Blog Issues enter the public taxonomy.
- [ ] The Tags index uses `/tags/` and each tag archive uses `/tags/{tag}/`, with registered canonical and output paths.
- [ ] Tag uniqueness and comparisons follow the accepted NFC and case-insensitive rules while preserving a deterministic display value.
- [ ] Tag pages link to canonical Blog routes and never construct `.html` URLs.
- [ ] Empty Blog tags still produce an intentional `/tags/` empty state without spurious archives.
- [ ] Escape1 and Escape2 render equivalent Tags pages from internal Tag and Blog models.
- [ ] Tests cover normalization, duplicate labels, ordering, empty input, and route collisions.
