# 23 — Deploy through Pages Artifact

**What to build:** Orchestrate site-repository builds and deploy validated output through GitHub Pages Artifact using least-privilege, short-lived GitHub credentials.

**Blocked by:** 22 — Contract the legacy compiler pipeline.

**Status:** ready-for-agent

- [ ] The deployment workflow lives with the site configuration and content repository rather than adding authoring or production credentials to the reusable compiler.
- [ ] It uses the official Pages artifact upload and deployment actions and does not commit generated HTML back to a branch.
- [ ] Permissions are limited to `contents: read`, `issues: read`, `pages: write`, and `id-token: write` where needed, using `GITHUB_TOKEN` rather than a personal PAT.
- [ ] Triggers cover path-filtered site-repository pushes, Issue opened, edited, labeled, unlabeled, closed, and reopened events, plus manual dispatch.
- [ ] Issue comments do not trigger static rebuilds.
- [ ] Workflow assertions verify official actions, exact triggers, minimum permissions, absence of PAT clone/push deployment, and use of validated compiler output.
- [ ] Repository guidance is updated to describe GitHub Actions as the Pages publication source rather than the `main` branch root.
