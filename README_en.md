<div align="center">

<img src="https://raw.githubusercontent.com/geoqiao/escaping/main/docs/assets/escaping-logo.png" alt="escaping logo" width="180">

# escaping

**Write in GitHub Issues. Get clean Markdown files for any site builder.**

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![GitHub Issues](https://img.shields.io/badge/Content-GitHub_Issues-181717?logo=github)](https://docs.github.com/issues)
[![MIT License](https://img.shields.io/badge/License-MIT-22C55E)](https://github.com/geoqiao/escaping/blob/main/LICENSE)

**[中文](https://github.com/geoqiao/escaping/blob/main/README.md)** · **[Live site](https://geoqiao.me/)** · **[Quick start](#-quick-start)** · **[Maintainers](https://github.com/geoqiao/escaping/blob/main/docs/dual-repo-architecture.md)**

</div>

## What escaping does

`escaping` does one thing: it writes the published Issues of a repository as Markdown files.

| Layer | Who owns it | Defined by |
| --- | --- | --- |
| Content | You write Issues and publish them with labels | [Issue Content v1](https://github.com/geoqiao/escaping/blob/main/docs/contracts/issue-content-v1.md) |
| Export | `escaping-site export` selects, checks and resolves every value, then writes files | [Content Export v1](https://github.com/geoqiao/escaping/blob/main/docs/contracts/content-export-v1.md) |
| Site | The site code that reads those files: the theme | The site |
| Hosting | GitHub Pages, Cloudflare or any static host | The site |

How pages look, what their addresses are and where they are hosted is not decided by `escaping`.

## 🚀 Quick start

**Use the default theme.** Create a site with **Use this template** on
[escaping-template](https://github.com/geoqiao/escaping-template). The template holds a default
theme that reads the exported files and a ready workflow; you need no local Python and no PAT.
Follow the template's README.

**Write your own theme.** Any site builder that reads Markdown works. Run this in a workflow:

```bash
uvx escaping-site@0.6.0 export --config config.yaml --output src/content
```

Then let your site read `src/content`. See [Content Export v1](https://github.com/geoqiao/escaping/blob/main/docs/contracts/content-export-v1.md)
for the files and [Deployment](https://github.com/geoqiao/escaping/blob/main/docs/deployment.md) for the workflow.

## Writing

| Action | Result |
| --- | --- |
| `type:blog` + `published` | Exported as `blog/<slug>.md` |
| `type:idea` + `published` | Exported as `ideas/<issue_number>.md` |
| `type:about` + `published` | Exported as `about.md` |
| Edit a published Issue | The next export updates the file |
| Remove `published` | The next export deletes the file; closing an Issue does not unpublish it |

Only Issues by allowed authors are exported; whoever runs the workflow gains no author rights.
Classify with labels such as `tag:python`; names that differ only in case, spaces or underscores
are the same tag. Front matter is optional and sets the slug, description, creation date or
update date field by field. Keep a published slug stable.

If one Issue has a problem, for example an invalid tag, only that Issue is skipped and the rest is
exported; the command exits with status 2 and names the Issue and what to fix. A failed export
leaves the previous files as they were.

## The exported files

```text
src/content/
├── manifest.json
├── about.md
├── blog/<slug>.md
├── ideas/<issue_number>.md
└── .escaping-output
```

Every front matter value is resolved (`issue_number`, `title`, `slug`, `description`,
`created_date`, `update_date`, `tags` and more), and the body is the Markdown you wrote.
The same Issues always give the same bytes, so a workflow that commits the folder commits only
when content changed.

## Config

`escaping` reads three sections of `config.yaml`; the rest of the file is your site's:

```yaml
github:
  repo: alice/site            # optional on GitHub Actions
  allowed_authors: [alice]    # optional for a personal repository with a token
about:
  issue_number: 42            # optional: the oldest published About Issue
security:
  token_env: GITHUB_TOKEN     # the default
```

A mistyped field in these sections fails with a message that names it and suggests the correct
spelling. Messages never repeat the values you supplied.

## Upgrading from 0.5

From 0.6.0 `escaping` no longer builds a website: the `build` command, Jinja Themes, Quiet and
the Action are removed. A site keeps working unchanged while its workflow stays on
`geoqiao/escaping@v0.5.1`. To move to 0.6.0, see the
[CHANGELOG](https://github.com/geoqiao/escaping/blob/main/CHANGELOG.md#upgrading-from-05).

## Development

The [maintainer entry](https://github.com/geoqiao/escaping/blob/main/docs/dual-repo-architecture.md) lists architecture, contracts, tests
and ADRs; agents use [AGENTS.md](https://github.com/geoqiao/escaping/blob/main/AGENTS.md).

## License

[MIT](https://github.com/geoqiao/escaping/blob/main/LICENSE) © geoqiao
