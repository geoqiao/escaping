# 18 — Complete site-wide routes and SEO outputs

**What to build:** Make one RouteRegistry authoritative for every public page, output path, internal link, feed URL, and search-engine signal across all three themes.

**Blocked by:** 05 — Deliver the paginated Blog archive; 07 — Deliver Blog Tags; 08 — Deliver the Blog-only Atom feed; 09 — Deliver Ideas end to end; 10 — Deliver Issue-backed About; 11 — Deliver curated Projects; 17 — Complete the geoqiao.me content pages and comments.

**Status:** ready-for-agent

- [ ] The registry covers Home, Blog archive/detail/pagination, Ideas index/detail, About, Projects, Tags index/archives, Atom, sitemap, and robots routes with correct file or trailing-slash output mapping.
- [ ] Route values are NFC-normalized, compared case-folded, and checked globally against dynamically registered reserved routes before rendering.
- [ ] Canonical, internal, Atom, sitemap, Open Graph, Twitter Card, and JSON-LD URLs use the sole HTTPS origin `https://geoqiao.me` and the same route/origin builder.
- [ ] Home and About emit appropriate Person or WebSite structured data; Blog detail emits BlogPosting data.
- [ ] Sitemap and robots outputs are valid, complete, and consistent with canonical page membership.
- [ ] Historical `.html` Blog routes, aliases, redirects, title-derived slugs, and template URL concatenation are absent.
- [ ] Tests cover every route, output mapping, pagination, normalization and collision behavior, SEO metadata, XML validity, and all three themes.
