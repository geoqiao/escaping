# 10 — Deliver Issue-backed About

**What to build:** Build a timeless About page by combining reusable Site Profile identity with the detailed narrative from one explicitly configured published About Issue.

**Blocked by:** 04 — Compile a strict Blog detail tracer; 06 — Deliver Site Profile and Home.

**Status:** ready-for-agent

- [ ] About is selected by configured immutable Issue number and must be the only valid published About Issue.
- [ ] The build fails when the configured Issue is missing, a Pull Request, unauthorized, unpublished, incorrectly typed, duplicated by another valid published About, or otherwise invalid.
- [ ] About front matter permits description and `created_date`, forbids slug and tags, and follows every applicable accepted content-contract rule.
- [ ] The page combines Site Profile avatar, short bio, and links with Issue-authored narrative and expertise without creating another authority.
- [ ] `/about/` displays no created or publication date and binds comments to the configured Issue number.
- [ ] Escape1 and Escape2 render the same About model without accessing Issue objects or metadata.
- [ ] Tests cover the complete failure matrix, singleton enforcement, profile composition, hidden dates, sanitization, route, and comment binding.
