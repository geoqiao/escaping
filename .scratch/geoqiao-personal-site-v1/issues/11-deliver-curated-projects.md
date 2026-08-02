# 11 — Deliver curated Projects

**What to build:** Give visitors a curated Projects page whose author-selected entries remain useful even when optional GitHub enrichment is unavailable.

**Blocked by:** 02 — Enforce strict configuration and output containment.

**Status:** implemented

- [x] Each catalog entry strictly requires slug, title, repository, and summary, and supports featured status, numeric order, and typed fallback metadata.
- [x] Unknown catalog and fallback fields fail validation; fallback stars and forks are non-negative, language is textual, and topics are a list of text values.
- [x] Entries sort deterministically by order and then slug and link to GitHub without generating project detail routes.
- [x] Optional enrichment can add stars, forks, language, and topics; API failure uses fallback values when present or omits unavailable values without failing the build.
- [x] `/projects/` remains valid with an empty catalog and has an intentional empty state.
- [x] Escape1 and Escape2 render Projects from internal Project models.
- [x] Tests cover validation, ordering, featured selection, successful enrichment, partial and total failure, fallback behavior, and empty input.

## Implementation Record
- Added immutable `Project`/`ProjectsPage` models and `ProjectCompiler` for deterministic catalog ordering and graceful optional enrichment.
- Projects remain repository-owned and link directly to GitHub; no project detail routes are introduced.
- Added parameterized theme render coverage and strict config/fallback tests.
