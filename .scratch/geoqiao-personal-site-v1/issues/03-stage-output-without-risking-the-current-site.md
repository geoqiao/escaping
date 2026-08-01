# 03 — Stage output without risking the current site

**What to build:** Render candidate output in isolation so that a failed build cannot destroy or partially replace the last valid site.

**Blocked by:** 02 — Enforce strict configuration and output containment.

**Status:** ready-for-agent

- [ ] The compiler renders into a temporary location inside an approved containment boundary rather than directly into final output.
- [ ] Final output is untouched until the candidate render reports success.
- [ ] Parse, render, and validation failures clean up candidate output and preserve the previous final output byte-for-byte.
- [ ] A successful candidate can replace final output without exposing a partially copied tree.
- [ ] Core build code reports structured failures and does not terminate the process directly.
- [ ] Integration tests exercise successful replacement and representative failures through injected test collaborators without depending on production Issues.
