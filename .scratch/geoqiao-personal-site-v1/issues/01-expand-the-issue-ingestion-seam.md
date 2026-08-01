# 01 — Expand the Issue ingestion seam

**What to build:** Add a read-only GitHub ingestion seam that converts external Issues into immutable build-time snapshots while the current compiler path continues to work unchanged.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [x] The GitHub source fetches both open and closed Issues and records the fields required by the accepted Issue Content Contract, including PR identity, author, labels, body, and timestamps.
- [x] No PyGithub object crosses the adapter boundary into new compiler or rendering code.
- [x] Snapshot values are immutable and in-memory only; they are not persisted or treated as a second content authority.
- [x] The adapter performs no Issue creation, editing, labeling, publishing, or other mutation.
- [x] Adapter tests cover `state=all`, PR metadata, author and label values, timestamps, and deterministic snapshot conversion.
- [x] The existing build remains green while the new seam exists beside the legacy path.

## Comments

Implemented test-first and accepted after independent code review. Validation: 89 tests passed; changed-file Ruff, format, and ty checks passed. PR detection uses list-response metadata to avoid PyGithub per-Issue lazy-load requests.
