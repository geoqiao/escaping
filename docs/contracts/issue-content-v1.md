# Issue Content Contract v1

Status: **Accepted**

## 1. Purpose and scope

This contract defines the GitHub Issue representation consumed by `escaping`.
It is the output contract of an Issue Draft Uploader and the input of
`escaping-site export`, which writes the accepted content as Markdown files
([Content Export v1](content-export-v1.md)).

This contract does not define:

- the local draft Markdown format;
- how an Issue Draft Uploader authenticates or represents Local Drafts;
- project catalog files;
- how a Site renders a body, or the files of a Site;
- deployment workflows.

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY**
are normative requirements.

`escaping` makes no pages, addresses or feeds; the Site that reads the export
does. Where this contract names a path such as `/blog/{slug}/`, a page or
`/atom.xml`, it describes the Site this content is written for: the default
theme follows it, and a Site of your own SHOULD, so that content means the same
everywhere. Only what the export writes is checked by `escaping`. "The
compiler" is the part of `escaping` that selects and checks Issues, and "the
build" is one export run.

## 2. Authoritative inputs and derived values

Each authored value has exactly one authoritative input.

| Value | Authoritative input |
|---|---|
| Content ID | GitHub Issue number |
| Title | GitHub Issue title |
| Author | GitHub Issue author login |
| Markdown body | GitHub Issue body, excluding a declared front matter envelope |
| Content type | One `type:*` label |
| Publication state | `published` label |
| Tags | `tag:*` labels |
| Content creation date | Explicit `created_date`, otherwise the UTC date of Issue `created_at` |
| Content revision date | Explicit `update_date`, otherwise the content creation date |
| Publication/updated time | GitHub Issue `created_at` / `updated_at` |
| Blog slug | Explicit `slug`, otherwise the Issue number as a decimal string |
| Description | Explicit `description`, otherwise the first 50 code points of visible body text |
| Comment thread | The same GitHub Issue number |

The front matter MUST NOT duplicate values owned by GitHub native fields or
labels.

The GitHub Issue `created_at` timestamp is the publication time. The authored
`created_date` field records when the content itself was originally created.

Metadata overrides are optional and resolved independently: providing one field
MUST NOT require the others. An explicit invalid, null, or blank metadata value
MUST fail validation; it MUST NOT be replaced by a default. Defaults are derived
from the same Issue and sanitized body, not from a second content format, an AI
service, or a publication history ledger.

## 3. Eligibility and selection

An Issue is publishable only when all of the following are true:

1. it is not a Pull Request;
2. its author is present in the site `allowed_authors` list;
3. it has the `published` label;
4. it has exactly one supported content-type label;
5. it conforms to the type profile in this contract.

Supported content-type labels are:

- `type:blog`
- `type:idea`
- `type:about`

The compiler MUST query open and closed Issues (`state=all`). Open/closed state
MUST NOT determine publication. Closing a published Issue does not unpublish
it; removing the `published` label does.

Selection behavior:

- Pull Requests MUST be ignored.
- Issues by unauthorized authors MUST be ignored and reported as warnings.
- Issues without `published` MUST be treated as drafts and ignored. Their body
  and front matter MUST NOT be parsed or validated.
- A published Issue by an allowed author that violates a compiler-verifiable
  snapshot invariant MUST NOT be published. Section 11 says when that skips
  only the Issue and when it fails the build.

### 3.1 Snapshot and lifecycle invariants

A **snapshot invariant** can be validated from the current Issue set and site
configuration, such as required fields, label cardinality, safe paths, or route
collisions. The compiler MUST validate snapshot invariants.

A **lifecycle invariant** depends on prior state, such as whether a published
slug changed. Authors and any tooling that edits existing Issue Content MUST
preserve lifecycle invariants. The Issue Draft
Uploader only creates new Issues (published only on explicit authorization)
and therefore owns no post-creation lifecycle enforcement. A stateless compiler MUST NOT claim to
detect historical changes unless a version-controlled publication ledger is
supplied as an additional input.

## 4. Labels

### 4.1 Reserved labels

The following labels and prefixes are reserved by this contract:

- `published`
- `type:`
- `tag:`

Control labels (`published` and `type:*`) MUST NOT appear in the public Tags
taxonomy.

### 4.2 Type labels

A published Issue MUST have exactly one supported `type:*` label. Missing,
multiple, or unknown `type:*` labels are validation errors.

### 4.3 Tag labels

A Blog or Idea MAY use zero or more `tag:<key>` labels.

`<key>` is compared after Unicode NFC normalization and case folding, with runs
of spaces, underscores and hyphens turned into one hyphen. The result MUST:

- consist of letters or digits in any script, joined by single hyphens
  (`^[^\W_]+(?:-[^\W_]+)*$`);
- contain 1–50 characters.

Two labels with the same key are the same tag; the first spelling seen is the
display name. The tag page lives at `/tags/<key>/`, percent-encoded in links.

Reserved label matching and allowed-author login matching MUST use Unicode NFC
normalization followed by case-insensitive comparison. The emitted canonical
label spelling remains the lower-case form shown in this contract. Tags MAY be
added or removed after publication. Blog tag changes rebuild the Blog Tags
taxonomy.

Examples:

```text
tag:python
tag:risk-management
tag:Daily Life      # key daily-life
tag:机器学习
```

Idea tags MAY be displayed with Idea content but MUST NOT contribute to the Blog
Tags taxonomy. A `tag:*` label on About is a validation error.

Labels outside the reserved names and prefixes MAY be used for GitHub-side
workflow and are ignored by `escaping`.

## 5. Issue body envelope

An Issue body MAY contain only Markdown. Front matter is optional; when the
first line is exactly `---`, it declares an envelope and MUST satisfy all rules
below. Missing or malformed closing delimiters and invalid YAML MUST NOT fall
back to ordinary Markdown. A `slug:` phrase, fenced code, or a thematic break
elsewhere in the body does not declare metadata.

An optional envelope precedes the Markdown body:

```markdown
---
slug: rust-in-cloudflare-incident
description: A technical analysis of Rust's role in a Cloudflare incident.
created_date: "2026-07-20"
update_date: "2026-08-02"
---

Markdown body starts here.
```

Envelope requirements:

- A declared envelope's first line MUST be exactly `---`.
- The closing delimiter MUST be a line containing exactly `---`.
- The front matter document MUST be a YAML mapping.
- YAML MUST be parsed with a safe loader.
- Custom YAML tags and duplicate mapping keys MUST be rejected.
- Front matter MUST NOT exceed 16 KiB encoded as UTF-8.
- Unknown fields MUST be rejected.
- An empty envelope is an empty mapping; a non-mapping YAML value is invalid.
- If declared, the Markdown body begins after the closing delimiter. Without an
  envelope, the entire Issue body is Markdown.
- Only the separated Markdown body may be passed to the renderer. Authored
  metadata MUST NOT be passed as body content; ordinary prose mentioning its
  field names remains valid.

## 6. Front matter fields

### 6.1 Allowed fields

| Field | Type | Meaning |
|---|---|---|
| `slug` | string | Stable Blog route key |
| `description` | string | Plain-text SEO/social/feed summary |
| `created_date` | `YYYY-MM-DD` string | Actual content creation date |
| `update_date` | `YYYY-MM-DD` string | Date the author last revised the content |

### 6.2 Forbidden fields

The following fields MUST NOT appear because another source owns them:

- `title`
- `type`
- `tags`
- `published`
- `author`
- `issue_number`
- `created_at`
- `updated_at`
- `canonical_url`

### 6.3 `slug`

For Blog content, an omitted `slug` defaults to the immutable Issue number as a
decimal string. An explicit `slug` and the resolved current snapshot MUST:

- match `^[a-z0-9]+(?:-[a-z0-9]+)*$`;
- contain 1–80 characters;
- be unique among all Blog canonical slugs;
- not be `page`, which a Site needs for the pages of the Blog list.

As a lifecycle invariant, authors and editing tools MUST keep the slug unchanged
after its first publication.

Three to eight meaningful English words are recommended but are not a hard
validation rule.

The canonical Blog path is:

```text
/blog/{slug}/
```

### 6.4 `description`

For Blog, Idea, and About content, an explicit `description` MUST:

- be non-empty after trimming;
- be a scalar string containing no newline or control character;
- contain neither `<` nor `>`;
- contain no more than 300 Unicode code points.

The value is treated as plain text and MUST be escaped, never parsed as Markdown
or HTML.

A length of 80–160 code points is recommended for an authored override.

When omitted, the compiler MUST derive the description from the sanitized
rendered body's visible text, trim its ends, collapse whitespace runs to one
space, and take the first 50 Unicode code points. It MUST NOT append an ellipsis,
include front matter, image URLs or Mermaid diagram source, invent a
title-based summary, or rewrite the text. Inline text adjacency is preserved; block and line breaks separate words.
Image-only content has an empty derived description, not a fabricated caption.

The derived value is plain text, not a new authored field: code literals such as
`<button>` remain text and MUST be safely escaped, not reparsed as HTML. An empty
derived description is distinct from an explicitly empty invalid override. The
resolved description is used consistently for page meta, Open Graph/Twitter,
and applicable feed entry summaries.

### 6.5 `created_date`

An omitted `created_date` defaults to the UTC calendar date of the GitHub Issue
`created_at` timestamp. An authored value records the original content creation
date, which may be earlier, and MUST be a quoted string in `YYYY-MM-DD` format.
It MUST be a valid calendar date. Compilation normalizes accepted date spellings
to ASCII `YYYY-MM-DD` in SiteModel, including display and HTML `datetime` values;
for example, `"٢٠٢٦-01-01"` becomes `"2026-01-01"`. This does not rewrite Issue
content or narrow the accepted input rules.

This default or override changes neither collection order nor publication/feed
timestamps, which continue to use GitHub's native timestamps.

### 6.6 `update_date`

`update_date` records the day the author last revised the content. An authored
value MUST be a quoted string in `YYYY-MM-DD` format, MUST be a valid calendar
date and MUST NOT be earlier than the resolved `created_date`
(`UPDATE_DATE_BEFORE_CREATED`). It is normalized like `created_date`.

An omitted `update_date` defaults to the resolved `created_date`: the content
has not been revised. It does not default to the Issue `updated_at` timestamp,
because GitHub also moves that on a comment, a label or a title edit, none of
which revises the content. `updated_at` stays available unchanged.

Like `created_date`, it changes neither collection order nor publication/feed
timestamps.

## 7. Content type profiles

### 7.1 Blog

A Blog Issue:

- MUST have `type:blog` and `published`;
- MUST have a non-empty GitHub Issue title;
- MUST have a non-empty Markdown body;
- MUST NOT have a character that XML 1.0 forbids, such as U+0001, in its title,
  body or `description`, because the post goes into the Atom feed;
- MAY override `slug`, `description`, `created_date`, and `update_date`
  independently;
- MAY use `tag:*` labels;
- enters Home recent posts, `/blog/`, `/tags/`, `/atom.xml`, and sitemap;
- uses `/blog/{slug}/` as its canonical path;
- binds comments to its own Issue number.

### 7.2 Idea

One GitHub Issue represents exactly one Idea identity. Independent short records
MUST use independent Issues.

An Idea Issue:

- MUST have `type:idea` and `published`;
- MUST have a non-empty GitHub Issue title;
- MUST have a non-empty Markdown body;
- MUST NOT provide `slug`;
- MAY override `description`, `created_date`, and `update_date` independently;
- MAY use `tag:*` labels without contributing to the Blog Tags taxonomy;
- enters `/ideas/` and sitemap;
- does not enter Blog, Blog Tags, or `/atom.xml`;
- uses `/ideas/{issue_number}/` as its canonical path;
- uses its title as a concise summary and its Markdown body as the Idea content;
- binds comments to its own Issue number.

### 7.3 About

Site configuration MAY select an About Issue by immutable `about.issue_number`.
Without an explicit selection, the compiler selects the oldest valid,
published, allowed-author About Issue (see below). If none exists, the site
decides what its About page shows; the export has no `about.md`.

An About Issue:

- MUST match `about.issue_number` when explicitly configured;
- MUST have `type:about` and `published`;
- MUST have a non-empty GitHub Issue title and Markdown body;
- MUST NOT provide `slug`;
- MAY override `description`, `created_date`, and `update_date` independently;
- MUST NOT use `tag:*`;
- uses `/about/` as its canonical path;
- does not enter Blog, Ideas, Blog Tags, or `/atom.xml`;
- binds comments to its own Issue number.

An explicit selection has priority over discovery. If the
selected Issue is missing, is a Pull Request, is unauthorized, lacks `published`,
has the wrong type, or fails validation, the build MUST fail rather than fall
back. Without an explicit selection, the oldest published, allowed-author
`type:about` Issue is used; every other one is skipped and reported as an error
(`ABOUT_DUPLICATE`).

Failure to fetch necessary Issue inputs MUST NOT be misreported as an empty set
of Issues.

## 8. Publication lifecycle

The normative lifecycle is:

```text
Issue created with one type label, without published
    → draft editing and preview
    → published label added
    → first public build
    → later edits rebuild while preserving the Blog slug
```

Transitions:

- Add `published`: publish after full validation.
- Remove `published`: unpublish from the next successful build.
- Close/reopen: no publication effect.
- Edit title/body/allowed metadata: rebuild.
- Add/remove `tag:*`: rebuild Blog taxonomy.
- Add/edit comments: no static rebuild required.

### 8.1 Time semantics

- Blog and Idea collections MUST sort by Issue `created_at` descending.
- Ties MUST sort by Issue number descending.
- Blog and Idea pages display the normalized `created_date`; About MUST NOT
  display it. The omitted value uses the Issue's UTC creation date (section 6.5);
  there is no site-timezone Config field.
- `update_date` is written to the export; whether a page shows it is the
  Site's choice.
- An Atom entry `published` value uses the Issue `created_at` timestamp.
- An Atom entry `updated` value uses the GitHub Issue `updated_at` value.
- The Atom feed `updated` value uses the maximum `updated_at` among its entries.
- When the Blog collection is empty, a Site still serves a valid empty feed.
- The `published` label, not a future timestamp, is the only publication gate.

## 9. Body validity

A body MUST be renderable as GitHub-Flavored Markdown and its raw HTML MUST
pass the sanitizer; a body that does not is a content error and the Issue is
skipped. The default `description` (section 6.4) comes from that sanitized
rendering.

Front matter MUST NOT enable arbitrary template selection, code execution,
script injection, or per-content plugins in v1.

The export hands over the Markdown, not that rendering. The Site renders the
body and owns the safety of its own rendering
([Content Export v1, section 4.2](content-export-v1.md#42-body)).

## 10. Comments

Embedded comments are optional and disabled unless explicitly enabled in site
configuration. When enabled, Blog, Idea, and About Issue pages bind the widget
to the content's own GitHub Issue number. Mapping by title or full URL MUST NOT
be used because title and domain changes must not split the discussion thread.

When disabled, pages MUST NOT load the comment plugin or show a loading state
or a dead discussion anchor. A normal link to the source Issue MAY remain.
Enabled comments require the relevant GitHub App authorization; configuration
alone MUST NOT be presented as proof that writing comments works. Widget failure
MUST leave the body readable and provide a usable source-Issue fallback.

Pages that do not come from an Issue have no comment thread.

## 11. Slugs, tag keys and errors

Blog slugs MUST be unique among all Blog Issues; of two Issues with the same
slug, the lower Issue number keeps it and the other is skipped
(`SLUG_DUPLICATE`). Blog slugs are lower-case ASCII; tag keys are Unicode
letters and digits (NFC, case-folded) joined by hyphens.

Every validation error SHOULD include a stable error code and Issue number when
an Issue caused the error. All detectable content validation errors MUST be
collected and reported in one run. A Blog or Idea Issue with its own content
error is skipped and reported, and the rest is still published (the CLI exits
with status 2). Errors in Config or in the About Issue that
`about.issue_number` selects fail the run and publish nothing.

Addresses, and what happens when two pages want the same one, belong to the
Site.

## 12. Single current format

`escaping` supports only the current Issue Content Contract and performs
no runtime schema dispatch or legacy compatibility parsing. Historical Issues
that do not conform MUST be edited to the current format before publication.

## 13. Conforming Blog examples

### 13.1 Basic Issue without front matter

For Issue 128 titled `A small observation`, with labels `type:blog` and
`published`, a body of `Writing should be simple.` is sufficient. Its canonical
path is `/blog/128/`, its description is `Writing should be simple.`, and its
creation date defaults to the Issue's UTC creation date.

### 13.2 Explicit overrides

Issue title:

```text
使用 Rust 分析 Cloudflare 事故
```

Labels:

```text
type:blog
published
tag:rust
tag:cloudflare
```

Issue body:

```markdown
---
slug: rust-in-cloudflare-incident
description: Cloudflare 事故中的 Rust 技术分析与工程经验总结。
created_date: "2026-07-20"
---

这里开始写正文。
```

Canonical path:

```text
/blog/rust-in-cloudflare-incident/
```

## 14. Conforming Idea example

Issue title:

```text
工具的价值是减少上下文切换
```

Labels:

```text
type:idea
published
```

Issue body:

```markdown
---
description: 关于工具价值的一条想法。
created_date: "2026-07-20"
---

今天重新意识到，工具真正的价值不是功能数量，而是减少上下文切换。
```

Canonical path for Issue 128:

```text
/ideas/128/
```
