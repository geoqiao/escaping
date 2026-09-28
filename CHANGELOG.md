# Changelog

All notable changes to escaping are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/) (before 1.0, a minor version may
break things).

## [Unreleased]

### Changed

- **Quiet's fonts are smaller.** The heading font is now
  `assets/fonts/manrope-bold.woff2` (31 KB instead of a 95 KB TTF), and the
  unused Source Serif 4 font (194 KB) and the unused CSS variable `--serif`
  are gone. A Theme that extends Quiet and links to `manrope-bold.ttf` or
  `source-serif-4.ttf` must bring its own copy.
- **A site title, author or description the Atom feed cannot hold is a Config
  error.** The message names the field, as in `site.title: contains U+0001, a
  character the Atom feed cannot hold`, and the build stops before it reads
  any Issue.
- **escaping no longer depends on structlog.** The line that names a
  downloaded Theme's commit, and the traceback of an unexpected crash, are
  now plain lines on stderr. Log lines that repeated a reported error or
  warning are gone.

### Removed

- **Hints for settings that moved in 0.2 and 0.3.** A Config field such as
  `site.featured_posts` or `theme.source`, or `pages:` in a Theme's
  `theme.yaml`, is now reported as an unknown field instead of naming its new
  place. The [Theme guide](docs/themes/authoring.md#migrating-from-api-1-2-or-3)
  still lists where each one went.

### Fixed

- **One Blog post with a stray control character no longer stops the build.**
  A character that XML 1.0 forbids, such as U+0001, in a Blog post's title,
  body or `description` used to fail the whole build, because the post goes
  into the Atom feed. Now only that post is skipped with an error that names
  the character, and the rest of the site is published (exit code 2).
- **Quiet: a Theme that extends Quiet can drop the dark-mode button.** If its
  `header.html` had no button, Quiet's script stopped early, so the table of
  contents and the copy-code buttons were missing.

## [0.4.0] - 2026-09-28

A site can use a Theme straight from a folder of a public GitHub repository,
with one line in `config.yaml`. Themes are now sandboxed. Sites and Themes that
work with 0.3.0 keep working unless a template reaches into Python internals.

### Added

- **Themes from GitHub.** `theme.use: github.com/OWNER/REPOSITORY/FOLDER@VERSION`
  uses a Theme in a folder of a public GitHub repository; one repository can
  hold many Themes. The version (a tag, a branch or a commit SHA) is required.
  Each build and `escpe theme check` downloads that version without a token
  and deletes it afterwards; to update, change the version. `extends:` takes
  the same address, so a site can replace a few files of such a Theme and
  still update it by changing one line. See
  [Using a Theme from GitHub](docs/themes/authoring.md#using-a-theme-from-github).
- **A list of Themes** in [docs/themes/catalog.md](docs/themes/catalog.md).
  Add yours with a pull request.
- **The draft uploader skill can publish.** When the user explicitly
  authorizes publishing a draft, the new Issue gets the `published` label when
  it is created. Without that, it is created unpublished as before.

### Changed

- **Templates run in Jinja's sandbox**, so a Theme cannot reach Python
  internals, files or environment variables such as the token. A template
  that tries fails with `TEMPLATE_RENDER_FAILED` and the word "unsafe". Quiet
  and ordinary templates are unaffected.

## [0.3.0] - 2026-09-28

The site now decides which pages it has and where they live; a Theme only
supplies templates. Old addresses and sites under a path are handled by
escaping. Local Themes need a small update: read
[Upgrading from 0.2](#upgrading-from-02).

### Added

- **`pages` in `config.yaml`.** Each section (`blog`, `ideas`, `tags`,
  `projects`, `about`) takes `true`, `false` or a path, such as
  `blog: /posts/` or `tags: false`. The Blog cannot be turned off. `extra`
  adds pages such as `/now/` or one page per project, each rendered by a
  named Theme template. See [Pages](docs/site-inputs.md#pages).
- **`redirects` in `config.yaml`.** Old addresses (ending in `/` or `.html`)
  become pages that send visitors on to a current page. Chains are followed;
  circles and duplicates fail the build. A redirect whose target is no page,
  or whose source is a page again, is left out with the warning
  `REDIRECT_LEFT_OUT`. See [Redirects](docs/site-inputs.md#redirects).
- **Sites under a path**, such as a GitHub project site at
  `https://alice.github.io/notes/`. `site.url` and the Pages URL may carry a
  path. Page addresses, links in Issues and root-relative Config values move
  under it. See [Sites under a path](docs/site-inputs.md#sites-under-a-path).
- **Theme API 4.**
  - Only `blog.html` and `post.html` are required. Home, Ideas and tag pages
    fall back to `blog.html`; Ideas and About fall back to `post.html`.
    `tags.html` and `projects.html` are needed only when those pages are on,
    and the error names both fixes.
  - Every page has the same fields: `page.item`, `page.items`,
    `page.pagination`, `page.newer`, `page.older`, `page.tag`,
    `page.project`, `none` when unused. Posts, Ideas and About share the
    fields a single page shows.
  - The `url` filter: `{{ '/assets/site.css'|url }}` works at the root of a
    host and under a path.
- The Theme guide explains how to [share a Theme](docs/themes/authoring.md#sharing-a-theme).

### Changed

- **Breaking:** Themes declare `api: 4`. `pages` in `theme.yaml` is rejected
  with its new place (`pages.extra` in the site's `config.yaml`).
- **Breaking:** `page.post`, `page.idea`, `page.about` and `page.archive`
  are replaced; see
  [Migrating from API 1, 2 or 3](docs/themes/authoring.md#migrating-from-api-1-2-or-3).
- `site.routes.<name>` and `site.about` are `none` for a page that is off, and
  a Blog tag's `path` is `none` when the tag pages are off.
- The default menu follows `pages`: a moved Blog is linked at its new address;
  a page that is off is left out.
- A menu link to a page that is off says so, for example
  `(pages.tags is false)`.
- Issues of a section that is off are not published and get the warning
  `PAGE_OFF`.
- A profile About (no About Issue) has `body_html` with the bio.
- The output check reports `LINK_OUTSIDE_SITE` for a Theme address that
  leaves a site under a path, and names the `url` filter.
- `robots.txt` is written only for a site at the root of a host.
- A template that prints `none` fails with its file and line instead of
  writing the word None into the page.
- An About page from an Issue has an empty `created_date`: About shows no
  date.
- A description taken from the body leaves out Mermaid diagram source.
- A full URL into a folder the site does not write, such as a GitHub project
  site on the same host, is not checked as a page of this site. A broken link
  to a page suggests adding the old address to `redirects`.
- `escpe theme check` renders enough sample posts for a second Blog page and
  leaves out warnings about Issues that the Config names.
- The platform context written by the Action loses `pages_base_path`.
- Quiet uses the `url` filter and hides links to pages that are off.

### Upgrading from 0.2

1. **Pin the new version.** Change `uses: geoqiao/escaping@v0.2.0` to
   `@v0.3.0` (or its commit SHA) in the site workflow.
2. **Quiet only:** nothing else to do.
3. **A local Theme:** set `api: 4` and follow
   [Migrating from API 1, 2 or 3](docs/themes/authoring.md#migrating-from-api-1-2-or-3).
   Move any `pages:` from `theme.yaml`, unchanged, to `pages.extra` in
   `config.yaml`.
4. **A site script that wrote redirect pages** after the Action step: move
   its map into `redirects` and delete the script and its workflow step.
5. **Check locally (optional).** `escpe theme check --config config.yaml`.

To roll back, pin 0.2.0 again and restore the Theme's `api: 3` and `pages`
together with the old Config; 0.2 rejects `pages` and `redirects` in
`config.yaml`.

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
  to the [migration notes](docs/themes/authoring.md#migrating-from-api-1-2-or-3).
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
2. **Move Config fields.** The build reports any it finds as an error:

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
   [Migrating from API 1, 2 or 3](docs/themes/authoring.md#migrating-from-api-1-2-or-3). If
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

[0.4.0]: https://github.com/geoqiao/escaping/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/geoqiao/escaping/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/geoqiao/escaping/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/geoqiao/escaping/releases/tag/v0.1.0
