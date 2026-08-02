# 06 — Deliver Site Profile and Home

**What to build:** Present the configured site identity, concise Site Profile, navigation, and exactly five recent Blog posts on Home in both existing themes.

**Blocked by:** 04 — Compile a strict Blog detail tracer.

**Status:** ready-for-agent

- [x] Home Hero copy and calls to action come only from top-level site identity, Site Profile, and configured navigation.
- [x] Site Profile contributes avatar, short bio, and links without duplicating the long-form About narrative.
- [x] Home shows exactly the five newest Blog posts by accepted publication ordering, or all posts when fewer than five exist.
- [x] Home does not introduce another Markdown content authority or reinterpret Issue metadata.
- [x] Home remains coherent with no Blog posts and with optional profile values absent where the contract permits.
- [x] Escape1 and Escape2 render the same Home data through internal models and registered routes.
- [x] Tests establish Home as the sole owner of this composition and prevent later page tickets from replacing or duplicating it.

## Comments

Implemented test-first and approved after independent review. Validation: 624 tests passed; changed-tree Ruff/format, full ty, and diff checks passed. HomePage is the sole Home identity/profile/navigation authority, while the legacy adapter preserves existing `.html` content links until cutover.
