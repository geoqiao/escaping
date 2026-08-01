# 19 — Validate and atomically publish complete artifacts

**What to build:** Validate the candidate site as one coherent artifact and replace final output only when every required page, link, asset, and machine-readable document is sound.

**Blocked by:** 03 — Stage output without risking the current site; 18 — Complete site-wide routes and SEO outputs.

**Status:** ready-for-agent

- [ ] Artifact validation parses generated HTML and XML and checks required routes, internal links, assets, canonical URLs, metadata, sitemap, Atom, and output-path consistency.
- [ ] Validation runs against Escape1, Escape2, and geoqiao.me theme builds using the same acceptance matrix.
- [ ] Missing pages, broken internal links, missing assets, malformed XML, route disagreement, and canonical disagreement fail before final replacement.
- [ ] Successful replacement publishes the complete candidate atomically; no partially copied output is observable.
- [ ] Content, rendering, or artifact failures preserve the previous output and return structured diagnostics for CLI exit-code mapping.
- [ ] Empty Blog, Ideas, Projects, Tags, and Atom combinations still form a valid complete artifact.
- [ ] Integration tests exercise snapshots through model building, rendering, validation, and final replacement.
