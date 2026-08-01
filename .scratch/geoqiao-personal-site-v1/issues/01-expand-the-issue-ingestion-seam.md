# 01 — Expand the Issue ingestion seam

**What to build:** Add a read-only GitHub ingestion seam that converts external Issues into immutable build-time snapshots while the current compiler path continues to work unchanged.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] The GitHub source fetches both open and closed Issues and records the fields required by the accepted Issue Content Contract, including PR identity, author, labels, body, and timestamps.
- [ ] No PyGithub object crosses the adapter boundary into new compiler or rendering code.
- [ ] Snapshot values are immutable and in-memory only; they are not persisted or treated as a second content authority.
- [ ] The adapter performs no Issue creation, editing, labeling, publishing, or other mutation.
- [ ] Adapter tests cover `state=all`, PR metadata, author and label values, timestamps, and deterministic snapshot conversion.
- [ ] The existing build remains green while the new seam exists beside the legacy path.
