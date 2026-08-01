# 12 — Resolve locked themes and site overrides

**What to build:** Resolve declarative themes reproducibly from an immutable lock while allowing repository-owned templates and assets to override the locked theme.

**Blocked by:** 02 — Enforce strict configuration and output containment.

**Status:** ready-for-agent

- [ ] A strict theme lock identifies repository, full immutable commit, and supported theme API version.
- [ ] Builds use the exact locked commit from cache or fetch that exact commit when absent; they never follow a moving branch or tag.
- [ ] Theme upgrades occur only through an explicit update operation and do not happen as a side effect of normal builds.
- [ ] Site overrides resolve before locked-theme templates and assets without forking compiler logic.
- [ ] Manifest validation covers API version, declared capabilities, required templates, and required asset directories.
- [ ] Theme rendering uses StrictUndefined and fails clearly when the contract is incomplete.
- [ ] Themes remain declarative and cannot execute Python extensions or arbitrary runtime plugins.
- [ ] Tests cover cache hit, exact fetch, invalid commit, manifest mismatch, override precedence, missing variables, and explicit updates.
