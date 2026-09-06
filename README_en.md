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
| A complete personal site | Home, article archives, short ideas, curated projects, About, tags, RSS and search-engine discovery files |
| A simple default appearance | Quiet by default, with support for site-owned local Themes |
| Controlled publication | Content and link validation; the site workflow deploys only successful builds |

## Get started

Use **Use this template** at [escaping-template](https://github.com/geoqiao/escaping-template).
No local Python, PAT, or manually created publishing labels are required.

> **Public preview:** an existing production site's build and deployment have been verified;
> first-time template creation, automatic labels and the complete new-user initialization flow have not.

1. Create `username.github.io` (public for GitHub Free), keep Issues/Actions enabled, and select **GitHub Actions** in **Settings → Pages**.
2. Save an Issue with a title and Markdown body; wait for **Prepare missing labels only** to succeed, then refresh the label selector.
3. Add one of `type:blog`, `type:idea`, or `type:about`, plus `published` when ready, and check the Actions deployment.

Project-site subpaths are unsupported; an existing custom domain must serve an HTTPS root URL.
The [starter instructions](starter/README.md) cover the full setup, version selection and failure recovery.

## Everyday writing

| Action | Result |
| --- | --- |
| `type:blog` + `published` | Publish an article in Blog, RSS and applicable tag archives |
| `type:idea` + `published` | Publish one independent short idea; exclude it from Blog/RSS and display its tags without archives |
| `type:about` + `published` | Supply About content; without an About Issue, the site can use the public owner profile |
| Edit a published Issue | Update the site on the next successful build; GitHub remains authoritative after creation |
| Remove `published` | Unpublish on the next successful build; closing the Issue alone does not unpublish it |

Only content from allowed authors is published; the workflow actor does not automatically gain author permission.
Blogs can use labels such as `tag:python` and default to `/blog/{issue_number}/`.
Optional front matter overrides the slug, description or original creation date independently;
keep a published slug stable. See [Issue Content v1](docs/contracts/issue-content-v1.md) for rules and examples.

## Customize when needed

The template's `config.yaml` starts as `{}`. Override only the fields you need, for example:

```yaml
site:
  title: My notes
```

| What to change | Where to look |
| --- | --- |
| Title, profile, curated projects | [Example Config](config.example.yaml) and [field sources](docs/site-inputs.md); the example is not a mandatory-field checklist |
| Navigation | Home, Blog, Ideas, Projects, Tags, About, RSS by default; `site.navigation.items` replaces the whole menu, including `[]`, while the brand's Home link remains independent |
| Appearance | [Quiet](docs/themes/quiet.md) is the only built-in/default Theme; [local Themes](docs/themes/authoring.md) use API 2, without automatic remote downloads |
| Comments | Off by default; set `comments.enabled: true` and separately authorize the [Utterances App](https://github.com/apps/utterances). Profile About never has comments |
| Local builds | Require Python 3.14.x, uv and a token that can read the target Issues; see the [local build steps](docs/site-inputs.md#local-build) |

Organization-owned content repositories require explicit `github.allowed_authors`.
Missing fields use defaults; invalid explicit values fail rather than being ignored.
Output and local Theme paths are relative to the Config directory. Serve output as the HTTP document root,
not under an `/output/` URL prefix.

These instructions describe current source; a site's behavior depends on its selected generator version.
The former built-ins `geoqiao.me`, `Escape1`, and `Escape2` are removed: explicit selections fail instead of silently changing the design.
Before upgrading, [select Quiet or preserve a local copy](docs/themes/authoring.md#migrating-removed-built-in-themes).
For old APIs, comments and menus, follow the [migration checklist](docs/themes/authoring.md#migrating-from-api-1).
Configuring comments is not proof of posting; actual App/OAuth submission still needs separate verification.

## Development and maintenance

The [maintainer guide](docs/dual-repo-architecture.md) links architecture, contracts, tests and ADRs;
agents use [AGENTS.md](AGENTS.md). The [starter workflow](starter/.github/workflows/pages.yml) is the canonical
reusable deployment source; once copied, it is site-owned. Generator upgrades, local Theme migrations
and production deployment are separate operations.

## License

[MIT](LICENSE) © geoqiao
