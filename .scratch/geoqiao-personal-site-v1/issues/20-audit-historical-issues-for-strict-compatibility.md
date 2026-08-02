# 20 — Audit historical Issues for strict compatibility

**What to build:** Produce a read-only migration report showing exactly which historical published Issues must be edited before the single strict compiler cutover.

**Blocked by:** 18 — Complete site-wide routes and SEO outputs.

**Status:** implemented

- [x] The audit evaluates current repository Issues against the accepted Issue Content Contract and configured author/About policy without modifying GitHub.
- [x] Every incompatible published Issue is reported with Issue number, stable diagnostic code, affected field, and actionable explanation.
- [x] The report includes type and publication labels, front matter, required body, dates, slug syntax and collisions, tags, author eligibility, About singleton rules, and route collisions.
- [x] Unpublished Issues remain outside strict body validation, while the configured About exception is reported according to its failure matrix.
- [x] The audit explicitly identifies historical `.html` URLs that will be abandoned but does not propose aliases, redirects, or a legacy parser.
- [x] Re-running the audit on the same Issue snapshot produces the same report.

## Implementation Record

- The read-only snapshot audit is recorded in `geoqiao-issue-audit.md`.
- The pre-migration snapshot identified 34 legacy Blog Issues without strict metadata/labels and an invalid configured About selection.
- The post-migration snapshot is validated through the same `ContentCompiler` seam with no blocking diagnostics.
