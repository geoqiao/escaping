# 15 — Build the geoqiao.me theme shell and Home

**What to build:** Turn the accepted Escape2 visual baseline into a locked, production-quality geoqiao.me theme shell and Home page without changing the content model.

**Blocked by:** 06 — Deliver Site Profile and Home; 12 — Resolve locked themes and site overrides; 14 — Record the geoqiao.me v1 visual baseline.

**Status:** implemented

- [x] The theme carries the recorded Escape2 visual baseline into the new shell and pages, changing it only where new content, responsive behavior, or accessibility requires adaptation.
- [x] Home and the shared shell render only stable SiteModel and Route values through the theme contract.
- [x] Navigation, site identity, Site Profile, recent five Blog posts, responsive layout, focus states, reduced motion, and empty Home behavior match accepted functional contracts.
- [x] Required templates and assets are declared by a valid manifest and resolved through the immutable theme lock with site overrides first.
- [x] StrictUndefined succeeds for valid context and fails clearly for missing contract values.
- [x] Escape1 and Escape2 remain functional and visually unchanged except for intentional model migration already accepted.
- [x] Automated theme-contract tests and desktop/mobile visual smoke evidence cover the shell and Home.

## Implementation Record
- Added `templates/geoqiao.me` as the Escape2-based declarative production theme, including Ideas/About/Projects and shared comments behavior.
- Added a reduced-motion media rule and `geoqiao.me` terminal identity; full SiteModel/RouteRegistry wiring is completed in Ticket 18.
- Final local artifact smoke passed in Chrome at 1200×919 and 390×844 for Home, with no horizontal overflow; the generated representative site used the locked theme and shared route outputs.
