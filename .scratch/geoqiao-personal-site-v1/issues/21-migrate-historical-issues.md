# 21 — Migrate historical Issues

**What to build:** Manually edit the authoritative GitHub Issues so every intended published item satisfies the single accepted content format before strict cutover.

**Blocked by:** 20 — Audit historical Issues for strict compatibility.

**Status:** implemented

- [x] Each reported published Issue has the required native title, exactly one supported type label, correct optional tag labels, publication label, allowed author, and valid body front matter.
- [x] Blog Issues have valid unique slugs; Idea and About Issues have no slug; About has no tags and the configured About Issue is the sole valid published About.
- [x] `description` and quoted `created_date` values are accurate, and authored Markdown bodies remain non-empty with front matter separated correctly.
- [x] The site owner reviewed destructive URL changes and accepted that old `.html` links will not redirect.
- [x] A final read-only audit reports no blocking incompatibilities.
- [x] No local draft synchronization, automatic Issue update tool, legacy parser, or compatibility switch is introduced to perform this migration.

## Implementation Record

- Created About Issue #42 from the configured `profile.bio` and configured `about.issue_number: 42`.
- Migrated 34 Blog Issues using one-time `gh` operations: added metadata and labels while preserving each original Markdown body after the front matter delimiter.
- Verified all 34 body suffixes byte-for-byte against the pre-migration snapshot and compiled the result successfully.
