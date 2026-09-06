# Site deployment contract

Production orchestration belongs to the site repository, not `escaping`.

## Ownership

The site repository owns its real `config.yaml`, Pages workflow, custom domain, and any local
Theme. The generator owns `config.example.yaml`, package resources, the compiler, and the
reusable starter source.

The canonical [starter tree](../starter/) contains the same workflow and scripts used by local
delivery tests and template publication. Its workflow is not installed under this
repository's root `.github/workflows/`. Once copied, the site repository owns that automation.
Generator releases and template publication are separate steps; a generator release does not
by itself verify or publish the template. Do not substitute a personal site's Config, migration
history, or deployment workflow for the starter.

## Consumer naming contract

The product and GitHub repository are named `escaping`. Its Python distribution and only console
entry point are named `escpe`, while the import namespace remains `escaping`. The distribution is
intentionally not named `escaping` because that name belongs to an unrelated PyPI project. The
former `github-blog`/`github_blog` names and `blog-gen` command are not shipped, so external Pages
workflows and local automation must update their install/import/invocation references together
with the generator pin.

## Starter orchestration

The [canonical workflow](../starter/.github/workflows/pages.yml) is the source of truth for
reviewed action SHAs and executable steps; there is no separately maintained workflow template.
All jobs are restricted to the trusted default branch, and checkouts use the event SHA or the
resolved generator commit with `persist-credentials: false`. There is no PR/PR-target entry point.
Pushes have no path filter so every Config-relative local Theme path is covered. Concurrency is
isolated by ref with cancellation disabled, preventing other refs from replacing pending work
for the default branch.

| Job | Permission and responsibility |
| --- | --- |
| Labels | Only `issues: write`; no checkout or repository scripts. On the first saved Issue (or another supported event), GET each of four labels and POST only missing labels. Never PATCH user labels, label Issues, create About content, or comment. A 422 requires a successful re-read before being treated as a race. |
| Context | `contents: read`, `pages: read`; GET repository and actual Pages identity. Require GitHub Actions Pages source and a clean HTTPS root URL, even when Config overrides its URL. Never enable/configure Pages or modify domains. |
| Build | `contents: read`, `issues: read`; depend on successful labels/context jobs, select one generator identity, verify checkout HEAD, install source/lock non-editably in an external environment, then run the installed console. |
| Deploy | Only `pages: write`, `id-token: write`; depend on the successful build/upload, use the `github-pages` environment, and deploy only from the default branch. |

Users save their Issue, wait for label preparation, refresh the selector, then add one `type:*`
and `published` themselves. The same run can build after initialization; it does not depend on
`GITHUB_TOKEN` writes recursively triggering workflows. No mandatory manual dispatch or hand-built
labels are added to the normal journey. Actual template creation, event delivery, permissions,
Linux execution and Pages publication must be verified before declaring the public template ready;
a compatible existing site's deployment does not prove first-time template initialization.
Local HTTP fixtures and YAML checks do not prove those platform behaviors.

The step-scoped compiler token is mapped by the installed-Python adapter using
`read_config_overrides` and `security_from_config`, not a second YAML parser or Config format.
Reserved startup/platform variables and existing non-default names are rejected; `GITHUB_TOKEN`
is the explicit exception. Secrets are not put in argv, workflow outputs, Config, summaries or
artifacts. The parent only reads security/path inputs; the real installed CLI owns default
resolution and network reads, receiving the original `--config` plus non-secret `--context`.

`SITE_CONFIG` defaults to `config.yaml`; moving it requires updating that workflow environment
value. The upload path comes from the same strict PathsConfig/containment rules used by the
compiler, relative to the original Config directory, and is emitted only after successful
publication. A failed install/build never uploads a partial or old output as a new deployment.
Site-specific post-processing, when required, remains site-owned and must complete and validate
before upload; it is not shipped in the general starter.

## Stable and fixed versions

`ESCAPING_VERSION: stable` selects GitHub's official latest formal release exactly once per build,
rejecting drafts, prereleases, missing publication metadata and inconsistent identities. This is
GitHub's latest-release policy, not a custom maximum-semver or commit-date algorithm. Tags are
dereferenced through a bounded, cycle-checked Git-object chain to a full commit SHA; the actual
checkout HEAD must match. API-provided URLs are validated as identities, not followed, and HTTP
redirects cannot forward credentials to another origin. `target_commitish` is never treated as a
commit SHA, and failures never fall back to `main`.

Advanced users can select a full lowercase 40-character SHA, or a matching formal release tag
whose immutability GitHub confirms. Fixed selections skip latest. Each build records release/tag/
commit identity, actual Python/uv versions, project/lock hashes, wheel builder and installed
package versions. Source, resources and lock must come from that same reviewed revision.

Stable updates happen on the next normal build, not through polling, upgrade PRs or repository
write-back. The starter/workflow itself is site-owned and is not automatically upgraded with the
generator. The first formal release needs a previously verified fixed candidate, followed by a
real stable-resolution/install/build check before the public template is declared ready.

## Locked source installation

Use a reviewed source checkout/archive whose `pyproject.toml`, `uv.lock`, and package resources
come from the same immutable revision. Use uv 0.12.0 with an explicitly selected Python and a fresh,
dedicated environment outside the source directory. The starter's installer requires a pristine
Git checkout: before uv runs it rejects all untracked inputs, including ignored files that package
resource globs could include. It never cleans or deletes user files. Normal build-generated files
are allowed after installation; tracked source/lock changes are still rejected by the post-check.

```bash
export UV_PROJECT_ENVIRONMENT="/absolute/path/to/compiler-env"
uv sync --project "/absolute/path/to/compiler-source" --python 3.14 \
  --locked --no-default-groups --group build --no-editable \
  --no-build-isolation-package escpe
"$UV_PROJECT_ENVIRONMENT/bin/escpe" --config "/absolute/path/to/site/config.yaml"
```

Use Python 3.14.x and pass `--python 3.14`; changing only the environment directory does not override
`.python-version`. Use the installed console directly after sync, rather than an automatic
`uv run` sync that could reinstall the project as editable. On Windows, the console is
`Scripts/escpe.exe` instead of `bin/escpe`.

The generator's `build` dependency group locks its setuptools version and artifact hashes in
`uv.lock`, without making setuptools a runtime requirement of the distributed wheel. uv's
[package-specific isolation control](https://docs.astral.sh/uv/concepts/projects/config/#disabling-build-isolation)
installs the selected dependencies first, then builds `escpe` using that environment's backend.
A separate `--no-install-project` bootstrap is therefore unnecessary. A lone global
`--no-build-isolation` is not equivalent: in a fresh environment it can build the project before
setuptools is installed. This locks the generator backend, not unrelated third-party sdist build
backends; dependency wheel availability still needs validation for the deployment Python/platform.

Keep `build-system.requires` and the `build` group aligned and validate source installation before
publishing a generator revision: disabling isolation assumes the declared build requirements are
already satisfied. `--locked` rejects a missing/outdated lock without rewriting it and installation
checks downloaded artifact hashes; it does not independently validate PEP 518 requirements.
[`--frozen`](https://docs.astral.sh/uv/concepts/projects/sync/#checking-the-lockfile) skips lock
freshness checks and can silently omit new requirements, so it is not a substitute here. This
source-install contract does not change normal isolated wheel building or wheel consumption;
the site-owned workflow must adopt it explicitly when updating its generator pin.

## Site-owned attachments with immutable GitHub links

A site may keep attachment originals in its own repository and reference them in Issue
Content with full-commit GitHub URLs. Commit and push the files before updating Issue
Content; check that the public URLs serve the expected bytes. Image URLs use
`https://raw.githubusercontent.com/<owner>/<repo>/<full-sha>/<path>`. Downloads may use
the same raw URL; GitHub file-view links use `/blob/<full-sha>/<path>`.

This policy does not add an attachment downloader, URL rewriter, or asset-copy step to the
Site Compiler. Attachments remain external HTTPS resources in HTML and Atom. The compiler
checks URL safety but does not prove external resource availability. The site owns byte
verification, backups, migration maps, and keeping referenced commits reachable. Do not
squash away or delete the only retained reference to a published attachment commit.

Attachment-only changes do not require compiler asset copying. The generic starter still builds
on every default-branch push; the later Issue edit publishes changed references. Updating a file
at a new commit does not update existing pinned links.
Keep prior files and update references deliberately. Do not copy arbitrary `assets/` into
`output/` or weaken the artifact validator to accommodate this policy.

Historical migrations must back up Issue bodies, native metadata, labels, and comments;
preserve Issue numbers, slugs, authored dates and original files; preview exact URL-only
changes; and re-read the Issue before applying a patch to avoid overwriting intervening
edits. GitHub updates `updated_at` on a body edit, so Atom modification dates will change.
Issue edits can trigger production deployment and require the same production approval.

## Site-owned slug migration post-processing

The compiler owns the current canonical routes. A site repository may maintain an explicit,
temporary mapping for a published Blog slug migration and render and validate the final Pages
artifact after the compiler has produced the new canonical page:

```text
python3 scripts/render_slug_redirects.py --map content-migrations/blog-slugs-2026-08.json --output output --repository-root "$GITHUB_WORKSPACE"
```

This post-processing belongs to the site repository because the site owns the migration history,
retirement timing, and Pages artifact. It must not infer slugs from titles or turn migration
entries into a general compiler feature. The current script accepts only slash-form Blog routes,
checks that the target exists, skips a source that is still the current canonical page, and
fails on ambiguous or missing source/target state.
The production step also validates the required smoke artifacts, redirect HTML, and the complete
artifact tree delta before the Pages artifact is uploaded; it is not only a renderer.

This is separate from historical `.html` Blog URLs. ADR-0003 still rejects `.html` aliases and
compatibility redirects; the site-owned mapping only covers explicit non-`.html` slug migrations.
The boundary is recorded in
[ADR-0005](adr/0005-site-owned-blog-slug-migration-redirects.md).

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
schema, routing, sanitization, and output validation reproducible. The release maintainer must
pass compatible consumer builds before publishing a stable release; fixed-version sites change
their selection only after consumer verification. Rollback selects the previously verified SHA
and runs the workflow again. If the site PR also changed `config.yaml` in a way the older generator rejects,
the rollback must revert that site Config commit together with the pin: `extra="forbid"` means
unknown fields fail, so re-pinning alone can leave a Config that the previous generator cannot load.

## Artifact verification

Before production cutover, verify at least:

- Home, Blog archive/detail, Ideas, About, Projects, and Tags routes;
- Theme CSS/JS/images and shared `comments.js`;
- canonical, Open Graph, Twitter, and JSON-LD URLs;
- Atom entry/self links, sitemap membership, and robots sitemap URL;
- no comment widget/script in rendered HTML by default; when enabled, Issue-number binding
  and light/dark synchronization;
- explicit site-owned slug migration pages, when a migration map is present;
- Site Orchestrator gating leaves the currently deployed artifact untouched when a build fails;
- compiler staging leaves existing local output unchanged when compilation or validation fails.

The site must be served from the artifact root. `output/` is a filesystem directory, not a URL
prefix.
