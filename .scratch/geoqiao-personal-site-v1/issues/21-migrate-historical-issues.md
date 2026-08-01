# 21 — Migrate historical Issues

**What to build:** Manually edit the authoritative GitHub Issues so every intended published item satisfies the single accepted content format before strict cutover.

**Blocked by:** 20 — Audit historical Issues for strict compatibility.

**Status:** ready-for-human

- [ ] Each reported published Issue has the required native title, exactly one supported type label, correct optional tag labels, publication label, allowed author, and valid body front matter.
- [ ] Blog Issues have valid unique slugs; Idea and About Issues have no slug; About has no tags and the configured About Issue is the sole valid published About.
- [ ] `description` and quoted `created_date` values are accurate, and authored Markdown bodies remain non-empty with front matter separated correctly.
- [ ] The site owner reviews destructive URL changes and accepts that old `.html` links will not redirect.
- [ ] A final read-only audit reports no blocking incompatibilities.
- [ ] No local draft synchronization, automatic Issue update tool, legacy parser, or compatibility switch is introduced to perform this migration.
