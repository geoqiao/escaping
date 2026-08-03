# Cut the site repository over to the reusable generator

Status: ready-for-human
Priority: P0
Blocked by: 01, 02, 03

## Outcome

Move the real Config and production Pages workflow to `geoqiao/geoqiao.github.io`; use the packaged default `geoqiao.me` Theme, pin the generator, and verify a branch artifact before production deployment.

## Acceptance

- Workflow pins a generator release or full commit SHA rather than `main`.
- Config/Theme/workflow changes trigger the build.
- Workflow passes the site Config explicitly and uploads output rooted at the site repository.
- A manual run verifies routes, assets, comments, canonical metadata, Atom, sitemap, and rollback.

## Notes

External production changes require explicit approval at execution time.

## Comments

The local site migration branch now owns `config.yaml`. Its workflow will be updated to a full generator commit after the verified generator branch is pushed; merge/deploy remains separately gated.
