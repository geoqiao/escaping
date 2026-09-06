# Your Issue-based personal site

**Maintainer preview: a public template and stable generator release have not yet been published.**
This directory is the template source, not an already-available “Use template” destination.
Do not use it to replace a live site's workflow before release and deployment verification.

## Start writing

Once the template is published:

1. Create your site repository from the template. Use `username.github.io`, or a site with an
   already-configured custom domain at its root. Keep Issues and Actions enabled. In repository
   **Settings → Pages**, select **Source: GitHub Actions**.
2. Save an Issue with a title and Markdown body; GitHub's normal image upload works. The workflow
   automatically prepares missing publishing labels. Wait for **Prepare missing labels only**
   to succeed, then refresh the saved Issue's label selector.
3. Add exactly one of `type:blog`, `type:idea`, or `type:about`, and add `published` when ready.
   Your label change starts the build. Check the Actions run for success and the deployed URL.

No local Python, front matter, personal access token, manually created labels, or required
“Run workflow” step is part of this path. Label preparation never edits your Issue or publishes
it for you; existing label colors and descriptions are preserved.

Remove `published` to unpublish on the next successful build. Closing an Issue does not unpublish
it. No About Issue is required: the generator can use the owner's public profile. Only selected,
authorized content is published; the workflow actor is not an author-permission default.

## Customize when needed

`config.yaml` starts as `{}`. The current generator defaults to Quiet, with Home, Blog, Ideas,
Projects, Tags, About and RSS in the menu. Comments are off; enabling them requires the YAML
boolean `true` for `comments.enabled`, not quoted text. Local Themes use Theme API `"2"`.

This is the only Site Config; the workflow supplies non-secret, verified repository and Pages
identity separately. You may override individual fields, for example:

```yaml
site:
  title: My notes
```

Missing values use generator defaults; invalid explicit values fail instead of being ignored.
For an organization-owned content repository, explicitly configure `github.allowed_authors`.
Projects are opt-in; repositories are not automatically listed.

For a local Theme, keep its templates, manifest and assets in your site repository and select
it with `theme.source: local`, `theme.name`, and `theme.path`. The path is relative to your Config,
not the workflow's working directory. Use a Theme compatible with your selected generator release.
Every default-branch push triggers a build, including changes outside a conventional `theme/`
directory. If moving/renaming Config, also change `SITE_CONFIG` in `.github/workflows/pages.yml`.
Output paths remain relative to that original Config directory.

The workflow requires an existing GitHub Actions Pages source and a real HTTPS root URL. It only
reads Pages settings; it does not enable Pages, create a custom domain, edit DNS, or install Apps.
Project-site subpaths such as `/my-project/` are unsupported even if Config specifies a root URL.

## Versions, credentials and failures

| Setting or behavior | Meaning |
| --- | --- |
| `ESCAPING_VERSION: stable` | Each normal build resolves the official latest non-draft, non-prerelease release once, then installs its full commit SHA and dependency lock. Idle sites do not poll for releases. |
| Advanced fixed version | Replace `stable` in the workflow with a full lowercase 40-character commit SHA, or a formal release tag confirmed immutable by GitHub. Fixed versions do not chase latest. |
| Build summary | Records release/tag/commit, Python 3.14.x, uv, lock and project hashes, actual wheel builder and installed dependency versions. Keep this identity when reporting problems. |
| Token | Each job receives only its required short-lived `GITHUB_TOKEN` permissions. The compile step maps it to the Config-selected `security.token_env`; reserved process variables and collisions are rejected. Never put a token value in Config. |
| Failure | No release, failed API/identity/lock checks, or compiler errors stop upload/deployment. No fallback to `main`, empty content, or a different generator is performed. The previous deployed site remains in place. |

To recover from an incompatible release, choose a previously verified full SHA and revert any
incompatible Config/local Theme changes with it. The optional manual workflow trigger is for
recovery, not first-time label initialization. Following stable updates the generator, not this
workflow or your repository files; breaking changes still need a reviewed migration.

## For maintainers

Publish this exact directory, including hidden files, as the template tree after verification.
Do not add a generator checkout, personal Config, attachment history, migration scripts or site
output. Tests consume these same workflow/scripts; there is no second generated template copy.

Before public release, verify a fresh site with a fixed candidate, real repository event/permission
behavior, Linux installation and Pages publication. Then verify actual stable-release resolution
and installation; controlled HTTP fixtures alone do not establish those platform guarantees.
The root default appearance and optional integrations must also match the selected release.

Bundled automation is MIT-licensed. Choose a license for your own written content separately.
