# 03 — Stage output without risking the current site

**What to build:** Render candidate output in isolation so that a failed build cannot destroy or partially replace the last valid site.

**Blocked by:** 02 — Enforce strict configuration and output containment.

**Status:** ready-for-agent

- [x] The compiler renders into a temporary location inside an approved containment boundary rather than directly into final output.
- [x] Final output is untouched until the candidate render reports success.
- [x] Parse, render, and validation failures clean up candidate output and preserve the previous final output byte-for-byte.
- [x] A successful candidate can replace final output without exposing a partially copied tree.
- [x] Core build code reports structured failures and does not terminate the process directly.
- [x] Integration tests exercise successful replacement and representative failures through injected test collaborators without depending on production Issues.

## Comments

Implemented test-first and approved after four independent review passes. Validation: 289 tests passed; changed-file Ruff/format, full ty, and diff checks passed. Existing output uses an atomic Darwin/Linux directory exchange; unsupported platforms fail before replacing final output.
