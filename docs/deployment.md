# Site deployment contract

Production deployment belongs to the site repository, not to `escaping`. For
setup and recovery steps, use the [starter instructions](../starter/README.md);
this document is the maintainer-facing contract for delivery and safety.

## Ownership

The site repository owns its real `config.yaml`, its Pages workflow, its custom
domain and any local Theme. The generator owns the compiler, Quiet,
`config.example.yaml`, the reusable [Action](../action.yml) and the
[starter](../starter/) source.

The starter workflow is not installed in this repository's own
`.github/workflows/`. Once copied into a site, the site owns it. A generator
release does not publish or verify the template repository; that is a separate
step. Do not replace the starter with a personal site's Config, migration
history or workflow.

## Consumer naming contract

The product and GitHub repository are named `escaping`. The Python
distribution and its only console command are named `escpe`; the import
package is `escaping`. The distribution is not called `escaping` because that
name belongs to an unrelated PyPI project. The former `github-blog` /
`github_blog` names and the `blog-gen` command are not shipped.

## The reusable Action

A site workflow calls the generator as a GitHub Action:

```yaml
- id: site
  uses: geoqiao/escaping@v0.2.0   # or a full commit SHA
  with:
    config: config.yaml
- uses: actions/upload-pages-artifact@<sha>
  with:
    path: ${{ steps.site.outputs.output }}
```

| Input | Default | Meaning |
| --- | --- | --- |
| `config` | `config.yaml` | The site Config, relative to the repository root |
| `token` | `${{ github.token }}` | Reads the repository, its Issues and its Pages settings |

| Output | Meaning |
| --- | --- |
| `output` | Absolute path of the built site; pass it to `upload-pages-artifact` |
| `skipped-issues` | Comma-separated numbers of Issues left out because of their own errors; empty when none |

The Action runs three steps:

1. **Set up uv** 0.12.0 with a pinned `astral-sh/setup-uv`.
2. **Read the repository and Pages settings** with `gh api`. If Pages is not
   enabled, or its source is not GitHub Actions, the step fails with the
   annotation *"In Settings → Pages, set Source to GitHub Actions, then run the
   workflow again."* Otherwise it writes the
   [platform context](site-inputs.md#cli-inputs) (repository, owner, Pages
   root URL) to `$RUNNER_TEMP/escaping-context.json`.
3. **Build the site** with
   `uv run --project "$GITHUB_ACTION_PATH" --locked --python 3.14 … escpe build --config … --context … --token-env ESCAPING_TOKEN`.
   uv installs the generator's locked dependencies into a fresh environment
   under `$RUNNER_TEMP` and runs the pinned checkout of `escaping`. The token
   travels only in the `ESCAPING_TOKEN` environment variable, never in
   arguments or outputs. Exit status 2 (published with skipped Issues) becomes
   success for this step; the `skipped-issues` output carries the numbers.

Step scripts receive inputs through environment variables only, never by
`${{ }}` interpolation into the script text.

## Starter workflow

The [starter workflow](../starter/.github/workflows/pages.yml) is the source of
truth for the exact steps and pinned action SHAs.

It runs on Issue events (opened, edited, labeled, unlabeled, closed, reopened,
deleted, transferred), on every push and on manual dispatch. Jobs run only on
the default branch. The concurrency group `pages` queues runs without
cancelling a running one. The top-level `permissions` is empty; each job asks
for what it needs:

| Job | Permissions | What it does |
| --- | --- | --- |
| `labels` | `issues: write` | Creates the missing labels `published`, `type:blog`, `type:idea`, `type:about`. It compares names without case and never edits, removes or applies labels. If creating one fails, it checks again (another run may have created it) and fails only if the label is still missing. |
| `build` | `contents: read`, `issues: read`, `pages: read` | Checks out the site with `persist-credentials: false`, runs the Action and uploads its `output` as the Pages artifact. |
| `deploy` | `pages: write`, `id-token: write` | Deploys the artifact to the `github-pages` environment. Its last step fails when `skipped-issues` is not empty, pointing to the build job summary. |

So a run with one broken Issue still deploys everything else, and the run is
marked failed with the Issue numbers. A failed build uploads nothing, so the
site that is live stays as it was.

A user saves an Issue, adds one `type:*` label and `published`. The first Issue
event also creates the labels; the user may need to refresh the Issue page to
see them. The template's first-run journey on a brand-new repository must still
be verified on GitHub before calling the template ready; local tests do not
prove GitHub's event delivery, permissions or Pages publication.

## Versions

A site pins the generator in the `uses:` line: a release tag such as
`@v0.2.0`, or a full 40-character commit SHA. A SHA is the strongest pin,
because a tag can be moved. There is no automatic "latest" lookup: a site
changes version only when someone edits that line, after reading the
[CHANGELOG](../CHANGELOG.md).

The workflow itself is site-owned. Upgrading the generator does not update a
site's workflow; the CHANGELOG says when a workflow change is needed.

## Releasing the generator

Generator and site repositories cannot change at the same time. Release in
this order:

1. Merge the change to `main` with the full verification passing
   ([testing guide](agents/testing.md#验证命令)).
2. Set the version in `pyproject.toml`, run `uv lock`, add the CHANGELOG entry
   and tag the release (`vX.Y.Z`).
3. Build a real consumer site with the new tag on a branch, with its migrated
   Config, and check the output.
4. Update the site's `uses:` pin (and its Config, if the release needs it).
5. Deploy the site.

To roll back, pin the previous version again. If the site's Config changed
for the new version, revert that change in the same commit: every section
rejects unknown fields, so an older generator may not load a newer Config.
A rollback across 0.2.0 also needs the 0.1 workflow and scripts; see the
[CHANGELOG](../CHANGELOG.md#upgrading-from-01).

## Production changes

Deploying a production site, merging its default branch and changing its
Pages settings or domain are separate decisions from releasing the generator.
Make each one on purpose, after the consumer check in step 3 above. Automation
in this repository never enables or configures Pages, and never edits a site's
domain.

## Locked source installation

The Action installs the generator from its pinned checkout with the committed
`uv.lock`. To install from source elsewhere, use a checkout whose
`pyproject.toml`, `uv.lock` and package files come from the same revision,
uv 0.12.0, Python 3.14 and a fresh environment outside the source directory:

```bash
export UV_PROJECT_ENVIRONMENT="/absolute/path/to/escaping-env"
uv sync --project "/absolute/path/to/escaping" --python 3.14 \
  --locked --no-default-groups --group build --no-editable \
  --no-build-isolation-package escpe
"$UV_PROJECT_ENVIRONMENT/bin/escpe" build --config "/absolute/path/to/site/config.yaml"
```

On Windows the command is `Scripts/escpe.exe`.

- The `build` dependency group pins the setuptools version and hashes in
  `uv.lock` without making setuptools a runtime dependency.
  `--no-build-isolation-package escpe` builds `escpe` with that pinned backend;
  uv installs the other packages first. A plain `--no-build-isolation` is not
  the same: in a fresh environment it may build the project before setuptools
  is installed. Keep `build-system.requires` and the `build` group identical.
- `--locked` rejects a missing or outdated lock file without rewriting it, and
  installation checks the downloaded hashes. Do not use `--frozen` instead: it
  skips the freshness check and can silently leave out a new requirement.
- `--python 3.14` is needed; changing only the environment directory does not
  override `.python-version`.

## Site-owned attachments with immutable GitHub links

A site may keep attachment originals in its own repository and link them from
Issues with full-commit URLs:
`https://raw.githubusercontent.com/<owner>/<repo>/<full-sha>/<path>` for images
and downloads, `/blob/<full-sha>/<path>` for GitHub file views. Push the files
first and check that the URLs serve the expected bytes, then edit the Issue.

The compiler does not download, rewrite or copy attachments; they stay
external HTTPS links in HTML and Atom. It checks that URLs are safe, not that
they exist. The site owns the files, their backups and keeping the referenced
commits reachable: do not squash away the only commit a published link points
to. A newer version of a file needs a new link; old links keep the old bytes.

When migrating old content, back up Issue bodies, labels and comments first;
keep Issue numbers, slugs, dates and original files; preview URL-only changes;
and re-read each Issue right before editing it. A body edit changes
`updated_at`, so Atom dates change, and Issue edits can trigger a production
deployment.

## Site-owned slug migration post-processing

The compiler owns the current routes. A site may keep a temporary map such as
`/blog/old-slug/` → `/blog/new-slug/` and add redirect pages to the built
output after the Action step and before the upload step. The map, the script
and when to retire it belong to that site; neither the compiler nor the starter
ships them.

Such a step must accept only slash-form Blog routes (no `.html`), check that
each target exists, skip a source that is still a real page, and fail on
missing or ambiguous entries. Check the result before uploading. Do not guess
slugs from titles or weaken the compiler's checks.
[ADR-0003](adr/0003-drop-legacy-html-urls.md) still rejects `.html` aliases;
[ADR-0005](adr/0005-site-owned-blog-slug-migration-redirects.md) records the
site-owned boundary.

## Publication safety boundaries

The live site and the local output are protected separately:

- **Live site.** The deploy job runs only after a successful build and upload.
  A failed build leaves the deployed Pages artifact untouched.
- **Local output.** The compiler renders and checks a complete candidate in a
  staging directory first. If compiling, rendering or checking fails, the
  existing output is unchanged.
- **Replacing output.** The compiler renames the old output to a backup,
  moves the candidate into place and restores the backup if that fails. The
  output path may be missing for a moment between the renames; it is never
  filled file by file.
- **Ownership.** The output holds a `.escaping-output` marker. A non-empty
  directory without it is never replaced, so files escaping did not write are
  never deleted.

If removing the backup fails after a successful build, the build warns. If
restoring the backup also fails, the build fails and prints the output,
candidate and backup paths for manual recovery. Two builds writing to the same
output at once are not supported; there is no lock.

## Artifact verification

Before switching a production site to a new generator version, check at least:

- Home, Blog archive and posts, Ideas, About, Projects, Tags and `404.html`;
- Theme files under `/assets/` and shared scripts under `/assets/escaping/`
  (`comments.js`, `mermaid.js`, `mermaid/mermaid.min.js`);
- canonical, Open Graph, Twitter and JSON-LD URLs;
- Atom entry and self links, sitemap entries and the sitemap URL in
  `robots.txt`;
- no comment widget by default; when comments are enabled, the widget is bound
  to the Issue number and follows light/dark mode;
- redirect pages from a site-owned slug map, if the site has one;
- a failed build leaves the deployed site and the local output unchanged.

Serve the output directory as the web root. `output/` is a directory on disk,
not a URL prefix.
