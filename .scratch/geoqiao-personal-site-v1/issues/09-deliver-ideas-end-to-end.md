# 09 — Deliver Ideas end to end

**What to build:** Compile published Idea Issues into an Ideas index and stable detail pages with visible authored dates, display-only tags, and Issue-bound comments.

**Blocked by:** 04 — Compile a strict Blog detail tracer.

**Status:** ready-for-agent

- [ ] Idea content follows every applicable MUST and MUST NOT in the accepted Issue Content Contract, including required description, date, title, body, type, author, and publication rules.
- [ ] Idea front matter forbids slug and permits no fields beyond description and `created_date`.
- [ ] Idea routes use `/ideas/` and `/ideas/{issue_number}/`; identity and comment binding use the immutable Issue number.
- [ ] Idea pages display `created_date` and optional tags, but Idea tags never enter `/tags/` or Atom.
- [ ] Ideas sort by Issue `created_at` descending with Issue number descending as the tie-breaker.
- [ ] An empty Ideas collection still produces a valid intentional index.
- [ ] Escape1 and Escape2 render index and detail pages from internal Idea models.
- [ ] Tests cover forbidden metadata, tag isolation, sorting, routes, visible dates, comments, sanitization, and empty input.
