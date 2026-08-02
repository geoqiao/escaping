# 17 — Complete the geoqiao.me content pages and comments

**What to build:** Complete the production theme with Ideas, About, Projects, shared empty states, and reliable Issue-bound comments.

**Blocked by:** 09 — Deliver Ideas end to end; 10 — Deliver Issue-backed About; 11 — Deliver curated Projects; 16 — Add Blog and Tags to the geoqiao.me theme.

**Status:** implemented

- [x] Ideas index and detail, About, and Projects consistently apply the recorded Escape2 visual baseline without changing their accepted ownership, dates, tags, routes, or enrichment behavior.
- [x] Idea tags remain display-only, About displays no date, and Project enrichment failures remain visually coherent.
- [x] Empty Ideas and Projects states provide useful direction rather than generic placeholders.
- [x] Utterances binds to immutable Issue numbers and preserves configured repository fallback.
- [x] `theme_mode: auto` continues to synchronize light and dark modes through the existing message and mutation-observer behavior.
- [x] The Safari compatibility behavior removes lazy loading from the injected Utterances iframe so comments load reliably.
- [x] Theme-contract tests and desktop/mobile smoke evidence cover every visitor-facing route in the new theme.

## Implementation Record
- Added geoqiao.me Ideas/About/Projects templates from internal models and shared `_comments.html` behavior.
- Content and theme tracers verify dates, tag isolation, profile composition, Issue-number binding, sanitization, and empty states.
