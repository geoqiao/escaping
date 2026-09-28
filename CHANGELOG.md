# Changelog

All notable changes to escaping are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/) (before 1.0, a minor version may
break things).

## [0.2.0] - 2026-09-28

This release separates data from presentation. The generator turns Issues and
the Config into data and publishes safely; a Theme decides how pages look.
Quiet is now an ordinary Theme that ships with the package. Read
[Upgrading from 0.1](#upgrading-from-01) before you change your site's pin.

### Added

- **Theme API 3.** `theme.yaml` declares `api: 3` and may add:
  - `extends: quiet`, to override single templates or static files of Quiet;
  - typed `options` with defaults, set by the site under `theme.options`;
  - extra `pages`, either at one path or once per project
    (`for_each: projects`, for example `/projects/{slug}/`);
  - interface `strings` per language, picked by `site.language`.
- **Three ways to customize:** Quiet's options in `config.yaml`; a small
  `theme/` directory with `extends: quiet` that replaces one file; or a
  complete Theme. See the [Theme guide](docs/themes/authoring.md).
- **Quiet options:** `tagline`, `featured_posts`, `footer_text`,
  `show_powered_by`, `accent_color`, `accent_color_dark`, `comments_theme`,
  `comments_theme_mode`. See [Quiet](docs/themes/quiet.md).
- Quiet shows its interface in English or Chinese, following `site.language`
  (`zh`, `zh-CN`, … use Chinese). Search messages, the copy-code button and
  the message shown when comments cannot load follow it too.
- Quiet ships a `404.html` page.
- **Unicode tags.** `tag:机器学习` works. Spaces and underscores become hyphens
  and case is ignored, so `tag:Machine Learning` and `tag:machine_learning`
  are the same tag.
- **Reusable GitHub Action** (`uses: geoqiao/escaping@v0.2.0`). Inputs:
  `config`, `token`. Outputs: `output` (the directory to upload) and
  `skipped-issues`. It checks that Pages is set to GitHub Actions and says how
  to fix it when not.
- **Command line:**
  - `escpe build` (the default when no command is given);
  - `escpe theme check`, which renders sample content offline and reports
    Theme problems, including SEO warnings;
  - `--issues-json FILE`, to build from Issues saved with `gh api` instead of
    calling GitHub;
  - `--token-env NAME`, to choose the token variable for one run.
- **Exit status 2**: the site was published, but some Issues were skipped.
  On GitHub Actions the CLI also writes error annotations, a job summary with
  links to the Issues, and step outputs.
- **Output ownership marker.** Every output directory holds a
  `.escaping-output` file. A build refuses to replace a non-empty directory
  without it, so it never deletes files escaping did not write.
- A template error names the Theme file and line, for example
  `./theme/home.html line 2: … has no attribute 'tagline'`.
- Projects may have a `website` instead of, or in addition to, a
  `repository`. A project without a repository needs a `slug` and a `title`.

### Changed

- **A bad Issue no longer stops the build.** An Issue with its own content
  error (a bad tag, an invalid front-matter field, a duplicate slug) is left
  out and reported by number; the rest of the site is published. Config,
  Theme and About-selection errors still stop the build.
- With several published About Issues and no `about.issue_number`, the oldest
  one is used and the others are skipped. 0.1 failed the build.
- A `featured_posts` number that is not a published Blog post is left out with
  a warning. 0.1 failed the build.
- **Config layout.** Presentation settings moved from the site layer into
  `theme.options`. The Theme is chosen with `theme: {use: quiet}` or
  `theme: {use: ./theme}`.
- **Asset URLs.** Theme static files are published at `/assets/` (was
  `/templates/<name>/static/`). Shared scripts (comments, Mermaid) are at
  `/assets/escaping/`.
- Templates receive four names: `site`, `page`, `theme` (option values) and
  `t` (interface text).
- A project's default `slug` is its repository name in kebab case
  (`alice/My_Tool` → `my-tool`). In 0.1 it was the whole repository name in
  lower case. Two projects with the same slug fail with a message.
- Builds check only integrity: every page exists, internal links and assets
  resolve, output stays inside the site. SEO checks moved to
  `escpe theme check`, where they are warnings.
- The starter workflow is shorter. It calls the Action and needs no scripts
  in the site repository.
- The Theme directory is `themes/quiet` (lower case) inside the package.

### Removed

- Theme API 2. A Theme that declares `api_version: "2"` fails with a pointer
  to the [migration notes](docs/themes/authoring.md#migrating-from-api-2).
- Config fields `site.featured_posts`, `site.thesis`, `profile.tagline`,
  `branding`, `comments.theme`, `comments.theme_mode`, `theme.source`,
  `theme.name` and `theme.path`. The build names each one and says where it
  went.
- The starter's `.github/scripts/` (`install.sh`, `run_configured.py`,
  `github_platform.py`) and the `ESCAPING_VERSION: stable` release lookup.
  Sites pin a tag or a full commit SHA in `uses:` instead.

### Fixed

- The Action's build step now treats exit status 2 (Issues skipped) as
  success. Before, `bash -e` stopped the step before the status was mapped.
- A failed Issue fetch no longer prints the exception text, which could
  include request details. The message names only the error type.
- Local draft lint treats tags that differ only in case as duplicates, the
  same way the site build does.
- A YAML tag such as `!!python/object` in the Config is reported without
  repeating its text.
- An invalid `--issues-json` file is reported with its name, line and column.
- Errors about `paths.output` no longer repeat the configured value.

### Upgrading from 0.1

Do these steps in the site repository on a branch, build once, then merge.

1. **Replace the workflow.** Copy
   [`starter/.github/workflows/pages.yml`](starter/.github/workflows/pages.yml)
   over your `.github/workflows/pages.yml` and delete `.github/scripts/`.
   If your Config is not `config.yaml` at the repository root, change
   `config:` under the `uses: geoqiao/escaping@v0.2.0` step.
2. **Move Config fields.** The build lists every old field it finds:

   | 0.1 | 0.2 |
   | --- | --- |
   | `site.featured_posts` | `theme.options.featured_posts` |
   | `profile.tagline` | `theme.options.tagline` |
   | `branding.show_powered_by` | `theme.options.show_powered_by` (the rest of `branding` is gone; use `theme.options.footer_text` for a footer note) |
   | `comments.theme` | `theme.options.comments_theme` |
   | `comments.theme_mode` | `theme.options.comments_theme_mode` |
   | `site.thesis` | removed; declare it as an option of your own Theme |
   | `theme: {source: builtin, name: Quiet}` | `theme: {use: quiet}`, or leave `theme` out |
   | `theme: {source: local, name: x, path: theme}` | `theme: {use: ./theme}` |

3. **Update Theme asset URLs in the Config.** A root-relative
   `seo.social_image` or project `image` such as
   `/templates/my-theme/static/images/og.png` becomes `/assets/images/og.png`.
4. **Local Theme.** Follow
   [Migrating from API 2](docs/themes/authoring.md#migrating-from-api-2). If
   the Theme only changed a few parts of Quiet, a Theme with
   `extends: quiet` that keeps only those files is usually shorter.
5. **Projects.** If a Theme builds URLs from project slugs, check them: the
   default slug changed (see Changed). Set `slug:` explicitly to keep a
   specific value.
6. **Check locally (optional).** `escpe theme check --config config.yaml`
   renders sample pages with your Theme and options and needs no token.
7. **Old local output.** The first local build refuses an existing, non-empty
   output directory that has no `.escaping-output` file. Move out anything you
   want to keep and delete the directory once. GitHub Actions starts from a
   clean checkout, so this does not affect the workflow unless the output
   directory is committed.

Existing tag URLs stay the same: an ASCII tag such as `tag:python` still
publishes at `/tags/python/`.

To roll back, restore the 0.1 workflow, `.github/scripts/` and `config.yaml`
together from git history. The 0.1 generator rejects the new Config fields,
and 0.1 has no Action to pin.

## [0.1.0]

First release: Blog, Ideas, About, Projects, Tags, Atom, sitemap and search
from GitHub Issues, with the Quiet Theme and the starter workflow.

[0.2.0]: https://github.com/geoqiao/escaping/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/geoqiao/escaping/releases/tag/v0.1.0
