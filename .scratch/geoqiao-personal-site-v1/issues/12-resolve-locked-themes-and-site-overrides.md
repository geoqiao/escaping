# 12 — Resolve locked themes and site overrides

**What to build:** Resolve declarative themes reproducibly from an immutable lock while allowing repository-owned templates and assets to override the locked theme.

**Blocked by:** 02 — Enforce strict configuration and output containment.

**Status:** implemented

- [x] A strict theme lock identifies repository, full immutable commit, and supported theme API version.
- [x] Builds use the exact locked commit from cache or fetch that exact commit when absent; they never follow a moving branch or tag.
- [x] Theme upgrades occur only through an explicit update operation and do not happen as a side effect of normal builds.
- [x] Site overrides resolve before locked-theme templates and assets without forking compiler logic.
- [x] Manifest validation covers API version, declared capabilities, required templates, and required asset directories.
- [x] Theme rendering uses StrictUndefined and fails clearly when the contract is incomplete.
- [x] Themes remain declarative and cannot execute Python extensions or arbitrary runtime plugins.
- [x] Tests cover cache hit, exact fetch, invalid commit, manifest mismatch, override precedence, missing variables, and explicit updates.

## Implementation Record
- Added `ThemeResolver`/`ResolvedTheme` with full-SHA lock, cache-first resolution, exact-fetch callback, explicit update operation, manifest validation, override-first `ChoiceLoader`, and `StrictUndefined`.
- Added manifests for Escape1, Escape2, and `geoqiao.me`; no executable theme extension API exists.
- Added the repository-owned `templates/overrides/geoqiao.me/base.html` override to exercise override-first resolution without changing the locked theme snapshot.
