# 19 — Validate and atomically publish complete artifacts

**What to build:** Validate the candidate site as one coherent artifact and replace final output only when every required page, link, asset, and machine-readable document is sound.

**Blocked by:** 03 — Stage output without risking the current site; 18 — Complete site-wide routes and SEO outputs.

**Status:** implemented

- [x] Artifact validation parses generated HTML and XML and checks required routes, internal links, assets, canonical URLs, metadata, sitemap, Atom, and output-path consistency.
- [x] Validation runs against Escape1, Escape2, and geoqiao.me theme builds using the same acceptance matrix.
- [x] Missing pages, broken internal links, missing assets, malformed XML, route disagreement, and canonical disagreement fail before final replacement.
- [x] Successful replacement publishes the complete candidate atomically; no partially copied output is observable.
- [x] Content, rendering, or artifact failures preserve the previous output and return structured diagnostics for CLI exit-code mapping.
- [x] Empty Blog, Ideas, Projects, Tags, and Atom combinations still form a valid complete artifact.
- [x] Integration tests exercise snapshots through model building, rendering, validation, and final replacement.

## Implementation Record

- `SiteArtifactValidator` validates HTML, canonical/SEO metadata, internal links, assets, Atom, sitemap, and robots before publication.
- `OutputStagingService` preserves the previous output on failure and replaces a valid candidate atomically.
- The real migrated Issue snapshot generated 68 HTML files and 75 total output files successfully.
