# 02 — Enforce strict configuration and output containment

**What to build:** Make site configuration explicit and strict, and reject dangerous output locations before the compiler can render or delete anything.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [x] Unknown fields fail validation at every nested configuration level.
- [x] Configuration covers non-empty allowed authors, immutable About Issue selection, site identity, Site Profile, navigation, comments, positive Blog page size with default 10, canonical origin, language, and repository-owned project and theme inputs.
- [x] Site identity owns display name while Site Profile contains only avatar, short bio, and links.
- [x] Settings are explicitly injected into compiler and rendering collaborators; no global settings singleton is introduced.
- [x] GitHub credentials continue to use the environment-variable name selected by security configuration, with no hard-coded token variable.
- [x] Output containment rejects the filesystem root, repository root, current directory, parent directories, absolute escapes, and symlink escapes before mutation.
- [x] Configuration and containment behavior is covered by failing-first tests, including misspellings, nested unknown fields, invalid page sizes, and unsafe paths.

## Comments

Implemented test-first and accepted after three independent review passes. Validation: 236 full-suite tests passed before the final recursive duplicate-key test correction; the affected 183-test focused suite, changed-file Ruff/format, full ty, and diff checks passed afterward. Repository-wide Ruff retains the documented pre-existing `hello.py` failure.
