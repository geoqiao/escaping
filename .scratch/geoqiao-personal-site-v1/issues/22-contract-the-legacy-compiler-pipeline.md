# 22 — Contract the legacy compiler pipeline

**What to build:** Make the strict Site Compiler the only production path and remove the obsolete Issue-leaking, title-slug, `.html`, and pre-validation output behavior.

**Blocked by:** 19 — Validate and atomically publish complete artifacts; 21 — Migrate historical Issues.

**Status:** implemented

- [x] The default build uses the new GitHub adapter, internal models, RouteRegistry, renderer, artifact validator, and safe replacement path end to end.
- [x] PyGithub objects no longer reach orchestration, rendering, or templates.
- [x] The legacy parser, title-derived slug generation, `.html` page assembly, `issue_slugs` map, all-labels-as-tags behavior, and destructive pre-validation cleanup are removed.
- [x] No runtime switch, fallback parser, schema dispatcher, migration manifest, or persistent compatibility state remains.
- [x] Obsolete tests that enforce legacy coupling are replaced; retained tests use concrete snapshots and internal models rather than mock Issue objects.
- [x] CLI behavior maps structured reports to process exit status without core modules calling `sys.exit`.
- [x] Full pytest, Ruff, formatting check, type checking, template integrity, XML, and internal-link validation pass.

## Implementation Record

- Removed the old branch-root/PAT workflows from `escaping`.
- Added the site-repository Pages Artifact workflow template at `docs/deployment/geoqiao-pages.yml` and static workflow contract tests.
- Switched shipped configuration and active guidance from `G_T` to the Actions-provided `GITHUB_TOKEN`.
