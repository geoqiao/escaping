# 08 — Deliver the Blog-only Atom feed

**What to build:** Publish a valid Atom feed whose membership, timestamps, summaries, and links match the compiled Blog site.

**Blocked by:** 04 — Compile a strict Blog detail tracer.

**Status:** ready-for-agent

- [ ] The feed contains valid published Blog entries only; Idea, About, Projects, and unpublished content never appear.
- [ ] Entry publication uses Issue `created_at`, entry update uses Issue `updated_at`, and feed-level update follows the accepted contract.
- [ ] An empty Blog collection still produces valid Atom using build start time as feed-level updated.
- [ ] The feed includes a correct `rel="self"` link and canonical entry links from the RouteRegistry.
- [ ] Entry summaries use validated descriptions without leaking front matter.
- [ ] The feed is emitted at `/atom.xml` and parses as valid XML.
- [ ] Tests cover membership, ordering, timestamps, descriptions, self link, route consistency, and the empty-feed boundary.
