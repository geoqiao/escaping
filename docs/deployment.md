# Deployment

`escaping` deploys nothing. A site repository runs the export in its own
workflow, builds its site from the files and deploys it. This document is the
maintainer-facing contract for that workflow, for versions and for releases.
A new site copies a working setup from
[escaping-template](https://github.com/geoqiao/escaping-template).

## Ownership

The site repository owns its `config.yaml`, its site code, its workflows, its
host and its domain. `escaping` owns the `escaping-site` package on PyPI and
the two contracts. A site depends on the package, not on this repository.

## Naming

The product and GitHub repository are named `escaping`. The Python
distribution and its only console command are named `escaping-site`, and the
import package is `escaping_site`. The distribution is not plain `escaping`
because that name belongs to an unrelated PyPI project. The command was
`escpe` before 0.6.0.

## Running the export in a workflow

```yaml
- uses: astral-sh/setup-uv@<full commit SHA>
- name: Export the content
  id: content
  env:
    GITHUB_TOKEN: ${{ github.token }}
  run: |
    status=0
    uvx escaping-site@X.Y.Z export --config config.yaml --output src/content || status=$?
    # 2: exported, but some Issues were skipped; the skipped-issues output says which.
    if [ "$status" -eq 2 ]; then exit 0; fi
    exit "$status"
```

| Step output | Meaning |
| --- | --- |
| `output` | Absolute path of the exported content |
| `skipped-issues` | Comma-separated numbers of Issues left out because of their own errors; empty when none |

`escaping-site` writes both outputs itself when it runs in GitHub Actions. It
reads the token from `GITHUB_TOKEN` (or the variable named by `--token-env`).
With the token an empty Config exports the workflow's own repository
([Content Export v1](contracts/content-export-v1.md#71-config)). The job needs
`contents: read` and `issues: read`.

`escaping-site@X.Y.Z` fixes `escaping` itself; PyPI does not let a published
version change. Its dependencies are resolved when the step runs. Add
`--exclude-newer <date>` to fix those too.

After the export there are two ways to get a site out of it.

### Build in the same workflow

The workflow that exported the content runs the site builder next and deploys
the result, for example to GitHub Pages with `actions/upload-pages-artifact`
and `actions/deploy-pages`. The exported folder need not be committed. A last
step fails the run when `skipped-issues` is not empty, so one broken Issue
still deploys everything else and the run is marked failed with its number.

### Commit the export, for a host that builds on push

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
        env:
          SKIPPED: ${{ steps.content.outputs.skipped-issues }}
        run: |
          echo "::error::Issues $SKIPPED have errors and were left out."
          exit 1
```

- A failed export changes nothing, so the last good content stays committed
  and the site stays up.
- The export is the same for the same Issues, so an event that changes no
  content makes no commit and no build.
- A push made with `github.token` does not start other GitHub Actions
  workflows. A host connected through its own GitHub App still receives it.
- Do not edit the exported files by hand: the next export replaces the folder.

## Versions

A site pins the package version in its workflow: `escaping-site@X.Y.Z`. There
is no automatic "latest" lookup: a site changes version only when someone
edits that line, after reading the [CHANGELOG](../CHANGELOG.md).

The workflow and the site code are site-owned. A new `escaping` release does
not update them, and a change to the template does not reach sites already
made from it; the CHANGELOG says when a site must change something.

## Releasing

`escaping`, the template and a site cannot change at the same time. Release in
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
3. Run a real site with the new version on a branch and check its pages.
4. Update the pin in the
   [template repository](https://github.com/geoqiao/escaping-template), only
   now: a site made from the template installs the version it names, so that
   version must already be on PyPI.

To roll back, pin the previous version again.

Deploying a production site, merging its default branch and changing its host
or domain are separate decisions from releasing `escaping`. Automation in this
repository never touches a site.

## Locked source installation

To install from source instead of PyPI, use a checkout whose `pyproject.toml`,
`uv.lock` and package files come from the same revision, uv 0.12.20, Python
3.14 and a fresh environment outside the source directory:

```bash
export UV_PROJECT_ENVIRONMENT="/absolute/path/to/escaping-env"
uv sync --project "/absolute/path/to/escaping" --python 3.14 \
  --locked --no-default-groups --group build --no-editable \
  --no-build-isolation-package escaping-site
"$UV_PROJECT_ENVIRONMENT/bin/escaping-site" export --config "/absolute/path/to/site/config.yaml"
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

The export does not download, rewrite or copy attachments; they stay the
external HTTPS links the author wrote. The site owns the files, their backups
and keeping the referenced commits reachable: do not squash away the only
commit a published link points to.

When migrating old content, back up Issue bodies, labels and comments first;
keep Issue numbers, slugs, dates and original files; and re-read each Issue
right before editing it. A body edit changes `updated_at` and triggers the
site's workflow.

## Safety of the export folder

- **Staged.** The export writes a complete candidate in a staging directory
  first. If reading Issues, compiling or writing fails, the existing folder is
  unchanged.
- **Replaced by rename.** The old folder is renamed to a backup, the candidate
  is moved into place, and the backup is restored if that fails. The folder is
  never filled file by file.
- **Owned.** The folder holds a `.escaping-output` marker. A non-empty folder
  without it is never replaced, so files `escaping` did not write are never
  deleted. `--output` may be any folder inside the Config directory except
  `.git`.

If removing the backup fails after a successful export, the export warns. If
restoring the backup also fails, the export fails and prints the folder,
candidate and backup paths for manual recovery. Two exports writing to the
same folder at once are not supported; there is no lock.
