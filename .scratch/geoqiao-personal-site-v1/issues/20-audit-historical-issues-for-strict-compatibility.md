# 20 — Audit historical Issues for strict compatibility

**What to build:** Produce a read-only migration report showing exactly which historical published Issues must be edited before the single strict compiler cutover.

**Blocked by:** 18 — Complete site-wide routes and SEO outputs.

**Status:** ready-for-agent

- [ ] The audit evaluates current repository Issues against the accepted Issue Content Contract and configured author/About policy without modifying GitHub.
- [ ] Every incompatible published Issue is reported with Issue number, stable diagnostic code, affected field, and actionable explanation.
- [ ] The report includes type and publication labels, front matter, required body, dates, slug syntax and collisions, tags, author eligibility, About singleton rules, and route collisions.
- [ ] Unpublished Issues remain outside strict body validation, while the configured About exception is reported according to its failure matrix.
- [ ] The audit explicitly identifies historical `.html` URLs that will be abandoned but does not propose aliases, redirects, or a legacy parser.
- [ ] Re-running the audit on the same Issue snapshot produces the same report.
