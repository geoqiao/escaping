# 11 — Deliver curated Projects

**What to build:** Give visitors a curated Projects page whose author-selected entries remain useful even when optional GitHub enrichment is unavailable.

**Blocked by:** 02 — Enforce strict configuration and output containment.

**Status:** ready-for-agent

- [ ] Each catalog entry strictly requires slug, title, repository, and summary, and supports featured status, numeric order, and typed fallback metadata.
- [ ] Unknown catalog and fallback fields fail validation; fallback stars and forks are non-negative, language is textual, and topics are a list of text values.
- [ ] Entries sort deterministically by order and then slug and link to GitHub without generating project detail routes.
- [ ] Optional enrichment can add stars, forks, language, and topics; API failure uses fallback values when present or omits unavailable values without failing the build.
- [ ] `/projects/` remains valid with an empty catalog and has an intentional empty state.
- [ ] Escape1 and Escape2 render Projects from internal Project models.
- [ ] Tests cover validation, ordering, featured selection, successful enrichment, partial and total failure, fallback behavior, and empty input.
