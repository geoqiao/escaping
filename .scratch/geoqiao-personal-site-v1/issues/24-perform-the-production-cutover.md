# 24 — Perform the production cutover

**What to build:** Switch the live site to the validated strict compiler, Pages Artifact source, and canonical geoqiao.me domain, then verify the production result.

**Blocked by:** 21 — Migrate historical Issues; 22 — Contract the legacy compiler pipeline; 23 — Deploy through Pages Artifact.

**Status:** ready-for-human

- [ ] Repository Pages Settings are changed from branch-root publication to GitHub Actions.
- [ ] The canonical custom domain is configured as `geoqiao.me` and HTTPS enforcement is enabled.
- [ ] A manual production build completes through the new workflow without a PAT or generated-site commit.
- [ ] Home, Blog, Ideas, About, Projects, Tags, Atom, sitemap, robots, assets, comments, canonical metadata, and structured data are checked on the live HTTPS origin.
- [ ] Desktop and mobile smoke checks cover all visitor-facing page types, including Utterances theme synchronization and Safari loading behavior.
- [ ] The old GitHub Pages host behavior is observed and recorded without treating old `.html` paths as supported aliases.
- [ ] Cutover evidence, failures, and rollback conditions are recorded before the migration is declared complete.
