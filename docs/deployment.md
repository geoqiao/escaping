# Site deployment contract

Production orchestration belongs to the site repository, not `escaping`.

## Ownership

The site repository owns its real `config.yaml`, Pages workflow, custom domain, and any local
Theme. The generator owns only `config.example.yaml`, package resources, and the compiler.

## Consumer naming contract

The product and GitHub repository are named `escaping`. Its Python distribution and only console
entry point are named `escpe`, while the import namespace remains `escaping`. The distribution is
intentionally not named `escaping` because that name belongs to an unrelated PyPI project. The
former `github-blog`/`github_blog` names and `blog-gen` command are not shipped, so external Pages
workflows and local automation must update their install/import/invocation references together
with the generator pin.

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

## Publication safety boundaries

Live Pages protection and local output protection are separate:

- The Site Orchestrator deploy job depends on a successful build and artifact upload. A failed
  build therefore leaves the currently deployed Pages artifact untouched.
- The Site Compiler renders and validates a complete candidate in an owned staging directory
  before local publication begins. Compile, render, or validation failures leave an existing local
  output tree unchanged.
- Local publication uses portable directory renames. When output already exists, the compiler
  renames it to an owned sibling backup, promotes staging, and restores the backup if promotion
  fails. A successful local rebuild may briefly have no output path between those renames; it never
  copies a partial candidate into output file by file.

Backup cleanup failure is reported as a warning after the complete new output is published. If
rollback also fails, the build fails with explicit final, candidate, and backup paths and preserves
the recoverable trees for manual recovery.

Staging ownership checks run before each mutation. The interval between a check and its mutation is
a known local TOCTOU window and is not closed by this design. Concurrent local builds targeting the
same output directory are unsupported; the compiler does not provide a build lock.

## Why the compiler is pinned

Generator and site repositories cannot change atomically. A full SHA makes templates, Config
schema, routing, sanitization, and output validation reproducible. The site changes its pin only
after a consumer build succeeds. Rollback changes the pin to the previously verified SHA and runs
the workflow again. If the site PR also changed `config.yaml` in a way the older generator rejects,
the rollback must revert that site Config commit together with the pin: `extra="forbid"` means
unknown fields fail, so re-pinning alone can leave a Config that the previous generator cannot load.

## Artifact verification

Before production cutover, verify at least:

- Home, Blog archive/detail, Ideas, About, Projects, and Tags routes;
- Theme CSS/JS/images and shared `comments.js`;
- canonical, Open Graph, Twitter, and JSON-LD URLs;
- Atom entry/self links, sitemap membership, and robots sitemap URL;
- Issue-number comments and light/dark synchronization;
- Site Orchestrator gating leaves the currently deployed artifact untouched when a build fails;
- compiler staging leaves existing local output unchanged when compilation or validation fails.

The site must be served from the artifact root. `output/` is a filesystem directory, not a URL
prefix.
