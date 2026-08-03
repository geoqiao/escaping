# Store one registry-created Route per page

Status: ready-for-human
Priority: P1
Blocked by: 05

## Outcome

Delete page-specific Route copies and normalization passes. Preserve `RouteRegistry` as the sole construction and collision-validation module.

## Acceptance

- Every page stores a complete registry-created `Route`.
- Canonical/output mappings, route collision behavior, Atom, sitemap, robots, and internal links remain unchanged.
- No second route model or hand-built page Route remains.

## Comments

Deleted page-specific Route dataclasses. All rendered pages now hold the exact complete `Route` object created by the shared `RouteRegistry`; the site integration tracer checks identity.
