# Site deployment contract

Production deployment belongs to the site repository, not to `escaping`. For
setup and recovery steps, use the [starter instructions](../starter/README.md);
this document is the maintainer-facing contract for delivery and safety.

## Ownership

The site repository owns its real `config.yaml`, its Pages workflow, its custom
domain and any local Theme. The generator owns the compiler, Quiet,
`config.example.yaml`, the `escaping-site` package on PyPI and the
[starter](../starter/) source. A site depends on the package, not on this
repository; the [Action](../action.yml) remains for sites that already use it.

The starter workflow is not installed in this repository's own
`.github/workflows/`. Once copied into a site, the site owns it. A generator
release does not publish or verify the template repository; that is a separate
step. Do not replace the starter with a personal site's Config, migration
history or workflow.

## Consumer naming contract

The product and GitHub repository are named `escaping`. The Python
distribution and its only console command are named `escaping-site`, and the
import package is `escaping_site`, the same name as Python spells it. The
distribution is not plain `escaping` because that name belongs to an unrelated
PyPI project. The command was `escpe` before 0.6.0. The former `github-blog` /
`github_blog` names and the `blog-gen` command are not shipped.

## Building a site in a workflow

A site workflow installs the `escaping-site` package from PyPI at a fixed version and
runs it; this is what the starter does:

```yaml
- uses: astral-sh/setup-uv@<full commit SHA>
- id: site
  env:
    GITHUB_TOKEN: ${{ github.token }}
  run: |
    status=0
    uvx escaping-site@X.Y.Z build --config config.yaml || status=$?
    # 2: published, but some Issues were skipped; the skipped-issues output says which.
    if [ "$status" -eq 2 ]; then exit 0; fi
    exit "$status"
- uses: actions/upload-pages-artifact@<sha>
  with:
    path: ${{ steps.site.outputs.output }}
```

On GitHub Actions, when the Config leaves out `github.repo` or `site.url`,
the command reads the repository, its owner and its Pages address with the
token (`pages: read`), so `config.yaml` can be `{}`. If Pages is not enabled,
or its source is not GitHub Actions, the build fails with *"in Settings →
Pages, set Source to GitHub Actions, then run the workflow again"*. A Config
with both fields is never asked about Pages. The command writes the step
outputs `output` and `skipped-issues` itself.

## The Action, for sites that already use it

Before 0.6.0 a site workflow called the generator as a GitHub Action. It still
works and takes the same Config:

```yaml
- id: site
  uses: geoqiao/escaping@v0.5.1   # or a full commit SHA
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

1. **Set up uv** 0.12.20 with a pinned `astral-sh/setup-uv`.
2. **Read the repository and Pages settings** with `gh api`. If Pages is not
   enabled, or its source is not GitHub Actions, the step fails with the
   annotation *"In Settings → Pages, set Source to GitHub Actions, then run the
   workflow again."* Otherwise it writes the
   [platform context](site-inputs.md#cli-inputs) (repository, owner, Pages
   URL) to `$RUNNER_TEMP/escaping-context.json`.
3. **Build the site** with
   `uv run --project "$GITHUB_ACTION_PATH" --locked --python 3.14 … escaping-site build --config … --context … --token-env ESCAPING_TOKEN`.
   uv installs the generator's locked dependencies into a fresh environment
   under `$RUNNER_TEMP` and runs the pinned checkout of `escaping`. The token
   travels only in the `ESCAPING_TOKEN` environment variable, never in
   arguments or outputs. Exit status 2 (published with skipped Issues) becomes
   success for this step; the `skipped-issues` output carries the numbers.

Step scripts receive inputs through environment variables only, never by
`${{ }}` interpolation into the script text.

## Running the export in a workflow

A site built with another tool takes the content instead of the finished site
([Content Export v1](contracts/content-export-v1.md)). There is no Action for
it: the export needs nothing from GitHub Pages, so the workflow runs the
`escaping-site` package from PyPI at a fixed version:

```yaml
- uses: astral-sh/setup-uv@<full commit SHA>
- name: Export the content
  id: content
  env:
    GITHUB_TOKEN: ${{ github.token }}
  run: |
    status=0
    uvx --python 3.14 escaping-site@X.Y.Z export --config config.yaml || status=$?
    # 2: exported, but some Issues were skipped; the skipped-issues output says which.
    if [ "$status" -eq 2 ]; then exit 0; fi
    exit "$status"
# then run your own site builder; it reads ${{ steps.content.outputs.output }}
```

| Step output | Meaning |
| --- | --- |
| `output` | Absolute path of the exported content |
| `skipped-issues` | Comma-separated numbers of Issues left out because of their own errors; empty when none |

`escaping-site` writes both outputs itself when it runs in GitHub Actions. It reads
the token from `GITHUB_TOKEN` (or the variable named by `--token-env`). It
reads only the content sections of the Config (`github`, `about`,
`security`); with the token an empty Config exports the workflow's own
repository, and the rest of the file is free for the site builder
([Content Export v1](contracts/content-export-v1.md#71-config)). The job needs `contents: read` and `issues: read`. Building and
deploying the site, and failing the run when `skipped-issues` is not empty,
are the site workflow's steps.

`escaping-site@X.Y.Z` fixes `escaping` itself; PyPI does not let a published version
change. Its dependencies are resolved when the step runs. Add
`--exclude-newer <date>` to fix those too.

### Committing the export, for a host that builds on push

A host that builds from the repository, such as Cloudflare or Netlify, never
sees an Issue event. Commit the export instead: the Issue event runs the
workflow, the workflow pushes the changed Markdown, and the push starts the
host's build. The site build then needs neither `escaping` nor Python.

```yaml
'on':
  issues:
    types: [opened, edited, labeled, unlabeled, closed, reopened, deleted, transferred]
  workflow_dispatch:
permissions: {}
concurrency:
  group: content
  cancel-in-progress: false
jobs:
  content:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      issues: read
    steps:
      - uses: actions/checkout@<full commit SHA>
      - uses: astral-sh/setup-uv@<full commit SHA>
      - name: Export the content
        id: content
        env:
          GITHUB_TOKEN: ${{ github.token }}
        run: |
          status=0
          uvx escaping-site@X.Y.Z export --config config.yaml --output src/content || status=$?
          if [ "$status" -eq 2 ]; then exit 0; fi
          exit "$status"
      - name: Commit what changed
        run: |
          git add --all src/content
          if git diff --cached --quiet; then exit 0; fi
          git -c user.name='github-actions[bot]' \
            -c user.email='41898282+github-actions[bot]@users.noreply.github.com' \
            commit --message 'content: update from Issues'
          git pull --rebase
          git push
      - name: Report skipped Issues
        if: steps.content.outputs.skipped-issues != ''
        run: |
          echo "::error::Issues ${{ steps.content.outputs.skipped-issues }} have errors and were left out."
          exit 1
```

- A failed export changes nothing, so the last good content stays committed
  and the site stays up.
- The export is the same for the same Issues, so an event that changes no
  content makes no commit and no build.
- A push made with `github.token` does not start other GitHub Actions
  workflows. A host connected through its own GitHub App still receives it.
- Do not edit the exported files by hand: the next export replaces the folder.

## Starter workflow

The [starter workflow](../starter/.github/workflows/pages.yml) is the source of
truth for the exact steps and pinned action SHAs.

It runs on Issue events (opened, edited, labeled, unlabeled, closed, reopened,
deleted, transferred), on every push and on manual dispatch. Jobs run only on
the default branch. The concurrency group `pages-<ref>` queues runs of the
same branch without cancelling a running one; a push to another branch has its
own group, so it cannot replace a waiting deployment. The top-level
`permissions` is empty; each job asks for what it needs:

| Job | Permissions | What it does |
| --- | --- | --- |
| `labels` | `issues: write` | Creates the missing labels `published`, `type:blog`, `type:idea`, `type:about`. It compares names without case and never edits, removes or applies labels. If creating one fails, it checks again (another run may have created it) and fails only if the label is still missing. |
| `build` | `contents: read`, `issues: read`, `pages: read` | Checks out the site with `persist-credentials: false`, runs `escaping-site build` from the PyPI package and uploads its `output` as the Pages artifact. |
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

A site pins the package version in its workflow: `escaping-site@X.Y.Z`. PyPI does
not let a published version change. There is no automatic "latest" lookup: a
site changes version only when someone edits that line, after reading the
[CHANGELOG](../CHANGELOG.md). A site that still uses the Action pins a release
tag or a full commit SHA in its `uses:` line.

The workflow itself is site-owned. Upgrading the generator does not update a
site's workflow; the CHANGELOG says when a workflow change is needed.

## Releasing the generator

Generator and site repositories cannot change at the same time. Release in
this order:

1. Merge the change to `main` with the full verification passing
   ([testing guide](agents/testing.md#验证命令)).
2. Set the version in `pyproject.toml`, run `uv lock`, add the CHANGELOG entry
   and tag the release (`vX.Y.Z`). Pushing the tag runs the
   [release workflow](../.github/workflows/release.yml): it refuses a tag that
   differs from the package version, builds the sdist and the wheel, and
   publishes `escaping-site` to PyPI. PyPI trusts that workflow in the `pypi`
   environment (Trusted Publishing); no token is stored. A published version
   cannot be replaced, only yanked.
3. Build a real consumer site with the new tag on a branch, with its migrated
   Config, and check the output.
4. Update the site's `uses:` or `escaping-site@` pin (and its Config, if the release
   needs it).
5. Deploy the site.
6. Copy `starter/` into the
   [template repository](https://github.com/geoqiao/escaping-template) and
   merge it there, only now: a new site made from the template installs the
   version the starter names, so that version must already be on PyPI.
   `rsync -a --delete --exclude .git --exclude LICENSE starter/ <template checkout>/`

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
uv 0.12.20, Python 3.14 and a fresh environment outside the source directory:

```bash
export UV_PROJECT_ENVIRONMENT="/absolute/path/to/escaping-env"
uv sync --project "/absolute/path/to/escaping" --python 3.14 \
  --locked --no-default-groups --group build --no-editable \
  --no-build-isolation-package escaping-site
"$UV_PROJECT_ENVIRONMENT/bin/escaping-site" build --config "/absolute/path/to/site/config.yaml"
```

On Windows the command is `Scripts/escaping-site.exe`.

- The `build` dependency group pins the setuptools version and hashes in
  `uv.lock` without making setuptools a runtime dependency.
  `--no-build-isolation-package escaping-site` builds `escaping-site` with that pinned backend;
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

## Old addresses

List old addresses under `redirects` in `config.yaml` (see
[Redirects](site-inputs.md#redirects)); escaping writes the redirect pages and
checks their targets. A site that added redirect pages with its own script
after the Action step, as 0.2 required, moves the map into `redirects` and
removes the script and its workflow step
([ADR-0009](adr/0009-site-owned-pages-redirects-and-sub-paths.md)).

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
  `robots.txt` (only at the root of a host);
- no comment widget by default; when comments are enabled, the widget is bound
  to the Issue number and follows light/dark mode;
- redirect pages for the site's `redirects`, if it has any;
- a failed build leaves the deployed site and the local output unchanged.

Serve the output directory as the web root. `output/` is a directory on disk,
not a URL prefix. For a site under a path, serve it under that path (see
[Local build](site-inputs.md#local-build)).
