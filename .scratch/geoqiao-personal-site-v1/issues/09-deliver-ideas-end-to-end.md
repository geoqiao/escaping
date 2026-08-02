# 09 — Deliver Ideas end to end

**What to build:** Compile published Idea Issues into an Ideas index and stable detail pages with visible authored dates, display-only tags, and Issue-bound comments.

**Blocked by:** 04 — Compile a strict Blog detail tracer.

**Status:** implemented

- [x] Idea content follows every applicable MUST and MUST NOT in the accepted Issue Content Contract, including required description, date, title, body, type, author, and publication rules.
- [x] Idea front matter forbids slug and permits no fields beyond description and `created_date`.
- [x] Idea routes use `/ideas/` and `/ideas/{issue_number}/`; identity and comment binding use the immutable Issue number.
- [x] Idea pages display `created_date` and optional tags, but Idea tags never enter `/tags/` or Atom.
- [x] Ideas sort by Issue `created_at` descending with Issue number descending as the tie-breaker.
- [x] An empty Ideas collection still produces a valid intentional index.
- [x] Escape1 and Escape2 render index and detail pages from internal Idea models.
- [x] Tests cover forbidden metadata, tag isolation, sorting, routes, visible dates, comments, sanitization, and empty input.

## Implementation Record
- `ContentCompiler` is the single Issue Content parsing/validation seam for Blog, Idea, and About snapshots.
- Added immutable `Idea` model and parameterized Escape1/Escape2 index/detail render tracer.
- Idea tags are carried as display routes only; Blog tag aggregation consumes Blog models later in the strict integration batch.
