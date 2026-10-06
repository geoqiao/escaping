# Content Export Contract v1

Status: **Accepted**

## 1. Purpose and scope

This contract defines the files `escaping-site export` writes: the published Issue
Content of a repository as Markdown, for a site that another tool builds.
[Issue Content v1](issue-content-v1.md) stays the only definition of what an
Issue must look like; this contract defines only how accepted content leaves
`escaping`.

The export has no pages, routes, feeds, sitemap, search index, redirects,
Projects or Theme. The consuming site owns all of them.

The key words **MUST**, **MUST NOT** and **MAY** are normative requirements.

## 2. Selection

Selection, the About choice, slug uniqueness and every content rule are those
of Issue Content v1, applied by the same code as in `escaping-site build`. The
same Issues are exported as a build with every section on would publish. In
particular:

- an Issue without `published`, a Pull Request, and an Issue by an author
  outside `github.allowed_authors` are left out;
- a Blog or Idea Issue with its own content error is a Skipped Issue: it is
  left out and reported, the rest is exported, and the CLI exits with status 2;
- an error in the Config or in the About Issue that `about.issue_number`
  selects fails the export, and the previous export is left unchanged;
- every content type is exported. `pages` in the Config switches the pages of
  a built site and has no effect here; a consumer without a place for Ideas
  ignores `ideas/`. Likewise a slug is never refused for colliding with a
  page of a built site.

## 3. Directory

```text
<output>/
├── manifest.json
├── about.md               # only when an About Issue is published
├── blog/<slug>.md
├── ideas/<issue_number>.md
└── .escaping-output       # ownership marker
```

`--output` is relative to the Config directory and defaults to
`build/content`. It MUST start with one of the folders a built site may use
(`build`, `dist`, `output`, `public`, `_site`) and MUST NOT overlap
`paths.output`.

Every export replaces the directory as a whole, so a withdrawn Issue leaves no
file behind. The directory holds the `.escaping-output` marker; a non-empty
directory without it is never replaced. A consumer MUST NOT keep its own files
in this directory.

## 4. Markdown files

Each file is UTF-8 with LF line endings: a YAML front matter block, one empty
line, then the Markdown body.

```markdown
---
issue_number: 128
type: blog
title: 使用 Rust 分析 Cloudflare 事故
slug: rust-in-cloudflare-incident
description: Cloudflare 事故中的 Rust 技术分析与工程经验总结。
created_date: '2026-07-20'
update_date: '2026-08-02'
published_at: '2026-07-21T03:15:00Z'
updated_at: '2026-07-22T10:00:00Z'
tags:
- name: Rust
  key: rust
---

这里开始写正文。
```

### 4.1 Front matter

Every value is resolved: a field the author left out carries the default that
Issue Content v1 defines, so a consumer never recomputes one.

| Field | Blog | Idea | About | Value |
|---|---|---|---|---|
| `issue_number` | ✓ | ✓ | ✓ | Integer. Content ID and comment thread |
| `type` | ✓ | ✓ | ✓ | `blog`, `idea` or `about` |
| `title` | ✓ | ✓ | ✓ | Issue title, plain text |
| `slug` | ✓ | | | Route key, `^[a-z0-9]+(?:-[a-z0-9]+)*$`, unique among Blog files |
| `description` | ✓ | ✓ | ✓ | Plain text; may be empty when derived from an image-only body |
| `created_date` | ✓ | ✓ | | `YYYY-MM-DD` string; the date to display |
| `update_date` | ✓ | ✓ | | `YYYY-MM-DD` string; the day the author last revised the content, equal to `created_date` when never revised |
| `published_at` | ✓ | ✓ | | Issue `created_at` in UTC, `YYYY-MM-DDTHH:MM:SSZ` string |
| `updated_at` | ✓ | ✓ | | Issue `updated_at` in UTC, same format; it also moves on a comment or a label |
| `tags` | ✓ | ✓ | | List, possibly empty, of `name` (as displayed) and `key` (route key) |

Dates and times are YAML strings, not YAML timestamps. `title` and
`description` are plain text; a consumer MUST escape them and MUST NOT parse
them as Markdown or HTML.

The front matter is written by `escaping`. It is not the author's Issue front
matter, and it MAY gain fields in a later minor release; a consumer MUST ignore
fields it does not know.

### 4.2 Body

The body is the author's Markdown with the Issue's front matter envelope
removed and line endings turned into LF. Nothing else is changed: it is not
rendered, links are not rewritten and **raw HTML is not sanitized**.

A consumer therefore owns rendering and its safety:

- render GitHub-Flavored Markdown, so the page matches what the author sees in
  the Issue;
- sanitize raw HTML after rendering, or do not render raw HTML at all. The
  author list limits who can write a body; it is not a reason to skip this;
- attachments stay the external HTTPS links the author wrote.

`escaping` still renders and sanitizes each body while it exports, to derive
the default `description` and to apply the same content rules as a build. A
body the Site Compiler would refuse is a Skipped Issue here too.

## 5. `manifest.json`

```json
{
  "export_version": 1,
  "repository": "alice/site",
  "blog": [
    {"issue_number": 128, "slug": "rust-in-cloudflare-incident", "path": "blog/rust-in-cloudflare-incident.md"}
  ],
  "ideas": [{"issue_number": 131, "path": "ideas/131.md"}],
  "about": {"issue_number": 42, "path": "about.md"},
  "skipped_issues": []
}
```

- `export_version` is `1` for this contract. A consumer MUST check it. A
  change that removes or renames a field, or changes a value's meaning, gets a
  new number.
- `repository` is the content repository (`owner/name`), which is also where
  the comment threads live.
- `blog` and `ideas` are ordered newest first: by Issue `created_at`
  descending, then by Issue number descending. `path` is relative to the
  directory.
- `about` is `null` when no About Issue is published. The export has no
  Profile About; a consumer decides what its About page shows then.
- `skipped_issues` lists Skipped Issues in ascending order.

The manifest has no timestamp: the same Issues and Config give byte-identical
files.

## 6. Comments

A consumer that embeds Issue comments MUST bind the widget to
`issue_number` in `repository`, never to a title, slug or URL
(Issue Content v1, section 10). The discussion then stays with the content when
its address, its domain or the site builder changes.

## 7. Command

```bash
escaping-site export --config config.yaml [--output build/content] [--issues-json FILE]
```

`--repo`, `--context` and `--token-env` work as for `escaping-site build` (see
[Site inputs](../site-inputs.md#cli-inputs)). Exit status: 0 exported, 1 failed
with the previous export unchanged, 2 exported with Skipped Issues.

### 7.1 Config

The export reads three sections of the Config and checks only those:

| Field | Default |
|---|---|
| `github.repo` | `--repo`; on GitHub Actions, the repository of the workflow |
| `github.allowed_authors` | The owner of a personal repository, read from GitHub with the token |
| `about.issue_number` | The oldest published About Issue |
| `security.token_env` | `GITHUB_TOKEN` |

With a token on GitHub Actions an empty Config is enough. Everything else in
the file, `site` and `pages` included, belongs to whatever builds the site: it
is not read, and a section `escaping` does not know is not an error. So one
`config.yaml` can hold the consuming site's own settings.

One exception keeps a repository that both builds and exports safe: `--output`
MUST NOT overlap `paths.output` (default `output`).

The command is in the `escaping-site` package on PyPI. In GitHub Actions, run it at a
fixed version (see
[Deployment](../deployment.md#running-the-export-in-a-workflow)); it does not
need GitHub Pages.
