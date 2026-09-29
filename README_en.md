<div align="center">

<img src="docs/assets/escaping-logo.png" alt="escaping logo" width="180">

# escaping

**Write in GitHub Issues. Publish on your own personal site.**

Blog, Ideas, Projects, About, Tags and RSS, without a separate content management system.

**[中文](README.md)** · **[Live site](https://geoqiao.me/)** · **[Get started](#get-started)** · **[Maintainer guide](docs/dual-repo-architecture.md)**

</div>

## Why escaping?

| What you need | What escaping provides |
| --- | --- |
| Focus on writing | Issue titles and Markdown bodies, with labels controlling publication; front matter is optional |
| A complete personal site | Home, article archives, short ideas, curated projects, About, tags, RSS, a 404 page, static site search and search-engine discovery files |
| A simple default look you can change | The built-in Quiet Theme; change its options, override one file, or write a complete Theme |
| Controlled publication | An Issue with an error is skipped and named, and the rest is still published; a failed build leaves the live site unchanged |

## Get started

Use **Use this template** at [escaping-template](https://github.com/geoqiao/escaping-template).
No local Python, PAT, or manually created publishing labels are required.

> **Public preview:** the 0.4.0 Action builds a live site on GitHub; creating a new repository
> from the template, including the step that creates the labels, has not been tried on GitHub yet.

1. Create `username.github.io` (public for GitHub Free), keep Issues/Actions enabled, and in **Settings → Pages** set **Source** to **GitHub Actions**.
2. Save an Issue with a title and Markdown body. The workflow's `labels` job creates the publishing labels on its first run; refresh the Issue page if you do not see them.
3. Add one of `type:blog`, `type:idea`, or `type:about`, plus `published` when ready, and check the deployment in Actions.

The workflow runs the generator with `uses: geoqiao/escaping@v0.5.0`; the site repository needs no scripts.
A repository with another name works too: the site then lives at `username.github.io/<repository>/`, and escaping handles that path.
The [starter instructions](starter/README.md) cover the full setup, versions and failure recovery.

## Everyday writing

| Action | Result |
| --- | --- |
| `type:blog` + `published` | Publish an article in Blog, RSS and its tag archives |
| `type:idea` + `published` | Publish one independent short idea; it stays out of Blog/RSS and its tags are display-only |
| `type:about` + `published` | Supply the About page; without an About Issue, the site shows the public owner profile |
| Edit a published Issue | Update the site on the next successful build; GitHub remains authoritative after creation |
| Remove `published` | Unpublish on the next successful build; closing the Issue alone does not unpublish it |

Only content from allowed authors is published; the workflow actor does not automatically gain author permission.
Blogs use labels such as `tag:python` or `tag:机器学习`; spellings that differ only in case, spaces or underscores are the same tag.
Articles default to `/blog/{issue_number}/`. Optional front matter overrides the slug, description or original creation date
independently; keep a published slug stable. See [Issue Content v1](docs/contracts/issue-content-v1.md) for rules and examples.

If one Issue has an error, for example an invalid tag, only that Issue is left out and the rest is published.
The run is marked failed, and its summary names the Issue and what to fix.

## Customize when needed

The template's `config.yaml` starts as `{}`; your repository and GitHub profile fill in the title, author, URL, avatar and bio.
The Config has two layers: site fields (such as `site`, `profile`, `projects`) keep their meaning with any Theme;
appearance options go under `theme.options`, and the selected Theme defines which exist.

```yaml
site:
  title: My notes
  language: zh # also switches Quiet's interface text to Chinese
theme:
  use: quiet
  options:
    tagline: Writing about tools and learning
    featured_posts: [12, 7]
```

| What to change | Where to look |
| --- | --- |
| Title, profile, curated projects | [Example Config](config.example.yaml) and [field sources](docs/site-inputs.md); the example is not a mandatory-field checklist |
| Navigation | Home, Blog, Projects, Tags, About, RSS by default; Ideas can be added explicitly. `site.navigation.items` replaces the whole menu, including `[]`; see [Config sources](docs/site-inputs.md#missing-field-sources) |
| Appearance | See "Change the look" below |
| Social preview image | Set `seo.social_image` to an HTTPS URL or a Theme file such as `/assets/images/og.png`; Quiet emits Open Graph/Twitter image tags |
| Comments | Off by default; set `comments.enabled: true` and separately authorize the [Utterances App](https://github.com/apps/utterances). Profile About never has comments |
| Local builds | Require Python 3.14.x and uv; read Issues with a token, or build offline with `--issues-json`; see the [local build steps](docs/site-inputs.md#local-build) |

A mistyped field fails the build and suggests the correct spelling.
Error messages never repeat the values you wrote. Organization-owned content repositories require explicit `github.allowed_authors`.
Output and local Theme paths are relative to the Config directory. Serve the output as the web root, not under an `/output/` URL prefix.

### Change the look

Three ways, from simplest to most complete:

1. **Change Quiet's options** under `theme.options`, such as `tagline`, `featured_posts` or `accent_color`. See [Quiet](docs/themes/quiet.md) for all of them.
2. **Override one file.** Create a `theme/` directory with a `theme.yaml` containing `api: 4` and `extends: quiet`, add only the template or static file you want to replace, and set `theme: {use: ./theme}`. Everything else still comes from Quiet.
3. **Write your own Theme.** It needs only `blog.html` and `post.html`; see the [Theme guide](docs/themes/authoring.md). A Theme can also declare its own options and interface text.

You can also use a Theme someone put on GitHub: write `theme: {use: github.com/OWNER/REPOSITORY/FOLDER@v1.0.0}` in `config.yaml`. Each build downloads that version; to update, change the version. See the [Theme list](docs/themes/catalog.md) and [Using a Theme from GitHub](docs/themes/authoring.md#using-a-theme-from-github).

Which pages the site has, and where, is up to your `config.yaml`: `pages` turns a page off, moves it or adds one such as `/now/`, and `redirects` keeps old addresses working. See [Pages](docs/site-inputs.md#pages).

Then run `escpe theme check --config config.yaml`. It renders every page with sample content, offline and without a token, and reports Theme problems.

## Upgrading

A site pins the generator version in the workflow's `uses:` line (a tag or a full commit SHA); it never upgrades by itself.
Read the [CHANGELOG](CHANGELOG.md) before upgrading. You can pin the latest version directly: from 0.1, do the steps in
[Upgrading from 0.1](CHANGELOG.md#upgrading-from-01) and then [Upgrading from 0.2](CHANGELOG.md#upgrading-from-02);
from 0.2, only the second. For a local Theme, see [Theme migration](docs/themes/authoring.md#migrating-from-api-1-2-or-3).
Configuring comments is not proof of posting; actual App/OAuth submission still needs separate verification.

## Development and maintenance

The [maintainer guide](docs/dual-repo-architecture.md) links architecture, contracts, tests and ADRs;
agents use [AGENTS.md](AGENTS.md). The [starter workflow](starter/.github/workflows/pages.yml) is the reference
site workflow; once copied, it is site-owned. The generator runs as an [Action](action.yml). Generator upgrades,
local Theme migrations and production deployment are separate operations.

## License

[MIT](LICENSE) © geoqiao
