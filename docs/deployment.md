# Site deployment contract

Production orchestration belongs to the site repository, not `escaping`.

## Ownership

The site repository owns its real `config.yaml`, Pages workflow, custom domain, and any local
Theme. The generator owns only `config.example.yaml`, package resources, and the compiler.

## Consumer naming contract

The distribution and import namespace are both `escaping`; the only console entry point is
`escpe`. The former `github-blog`/`github_blog` names and `blog-gen` command are intentionally
not shipped, so external Pages workflows and local automation must update their install/import/
invocation references together with the generator pin.

A production workflow must:

1. check out the site repository;
2. check out `geoqiao/escaping` at a release or full 40-character commit SHA, never a moving
   `main` ref;
3. install the pinned project with `uv run --project` and `--frozen`;
4. invoke `escpe --config "$GITHUB_WORKSPACE/config.yaml"` explicitly;
5. upload `$GITHUB_WORKSPACE/output` as the Pages artifact;
6. use `${{ github.token }}` through the Config-selected `GITHUB_TOKEN` variable.

Config, workflow, `CNAME`, and local Theme changes should trigger a build. Issue events may also
trigger it because Issues are the content source. Branch/PR validation may build and upload an
artifact, but the deploy job must be guarded to `refs/heads/main`.

## Why the compiler is pinned

Generator and site repositories cannot change atomically. A full SHA makes templates, Config
schema, routing, sanitization, and output validation reproducible. The site changes its pin only
after a consumer build succeeds. Rollback is changing the pin to the previously verified SHA and
running the workflow again.

## Artifact verification

Before production cutover, verify at least:

- Home, Blog archive/detail, Ideas, About, Projects, and Tags routes;
- Theme CSS/JS/images and shared `comments.js`;
- canonical, Open Graph, Twitter, and JSON-LD URLs;
- Atom entry/self links, sitemap membership, and robots sitemap URL;
- Issue-number comments and light/dark synchronization;
- failed builds leave the currently deployed artifact untouched.

The site must be served from the artifact root. `output/` is a filesystem directory, not a URL
prefix.
