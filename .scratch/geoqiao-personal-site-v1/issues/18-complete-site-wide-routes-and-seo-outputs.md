# 18 — Complete site-wide routes and SEO outputs

**What to build:** Make one RouteRegistry authoritative for every public page, output path, internal link, feed URL, and search-engine signal across all three themes.

**Blocked by:** 05 — Deliver the paginated Blog archive; 07 — Deliver Blog Tags; 08 — Deliver the Blog-only Atom feed; 09 — Deliver Ideas end to end; 10 — Deliver Issue-backed About; 11 — Deliver curated Projects; 17 — Complete the geoqiao.me content pages and comments.

**Status:** implemented

- [x] The registry covers Home, Blog archive/detail/pagination, Ideas index/detail, About, Projects, Tags index/archives, Atom, sitemap, and robots routes with correct file or trailing-slash output mapping.
- [x] Route values are NFC-normalized, compared case-folded, and checked globally against dynamically registered reserved routes before rendering.
- [x] Canonical, internal, Atom, sitemap, Open Graph, Twitter Card, and JSON-LD URLs use the sole HTTPS origin `https://geoqiao.me` and the same route/origin builder.
- [x] Home and About emit appropriate Person or WebSite structured data; Blog detail emits BlogPosting data.
- [x] Sitemap and robots outputs are valid, complete, and consistent with canonical page membership.
- [x] Historical `.html` Blog routes, aliases, redirects, title-derived slugs, and template URL concatenation are absent.
- [x] Tests cover every route, output mapping, pagination, normalization and collision behavior, SEO metadata, XML validity, and all three themes.

## Implementation Record
- Added `SiteModel`, a shared `RouteRegistry`, strict `SiteCompiler`/CLI orchestration, and `SiteArtifactValidator` for complete output validation.
- Replaced legacy render adapters and `.html` writers with directory-index routes; canonical, internal, Atom, sitemap, robots, OG, Twitter, and JSON-LD URLs resolve from the same registry.
- Added the representative content-to-artifact tracer covering Home, Blog, Ideas, About, Projects, Tags, XML, sanitization, and comment Issue numbers.
- The real migrated Issue snapshot generated 68 HTML pages and 68 sitemap URLs, with valid Atom/XML, HTTPS-only metadata, no visible front matter, Issue-number comments, and no legacy `.html` routes. Local Chrome smoke remains green across all six visitor-facing sections.
