# Issue Content Contract v1

Status: **Accepted**

## 1. Purpose and scope

This contract defines the GitHub Issue representation consumed by `escaping`.
It is the output contract shared by an Issue Draft Uploader and the Site
Compiler.

This contract does not define:

- the local draft Markdown format;
- how an Issue Draft Uploader authenticates or represents Local Drafts;
- project catalog files;
- theme APIs;
- deployment workflows.

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY**
are normative requirements.

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
  snapshot invariant MUST fail the build.

### 3.1 Snapshot and lifecycle invariants

A **snapshot invariant** can be validated from the current Issue set and site
configuration, such as required fields, label cardinality, safe paths, or route
collisions. The compiler MUST validate snapshot invariants.

A **lifecycle invariant** depends on prior state, such as whether a published
slug changed. Authors and any tooling that edits existing Issue Content MUST
preserve lifecycle invariants. The Issue Draft
Uploader creates only new, unpublished Issues and therefore owns no
post-creation lifecycle enforcement. A stateless compiler MUST NOT claim to
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

For v1, `<key>` MUST:

- match `^[a-z0-9]+(?:-[a-z0-9]+)*$`;
- contain 1–50 characters.

Reserved label matching and allowed-author login matching MUST use Unicode NFC
normalization followed by case-insensitive comparison. The emitted canonical
label spelling remains the lower-case form shown in this contract. Tags MAY be
added or removed after publication. Blog tag changes rebuild the Blog Tags
taxonomy.

Examples:

```text
tag:python
tag:risk-management
tag:daily-life
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
- not collide with a reserved route.

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
include front matter or image URLs, invent a title-based summary, or rewrite the
text. Inline text adjacency is preserved; block and line breaks separate words.
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
It MUST be a valid calendar date.

This default or override changes neither collection order nor publication/feed
timestamps, which continue to use GitHub's native timestamps.

## 7. Content type profiles

### 7.1 Blog

A Blog Issue:

- MUST have `type:blog` and `published`;
- MUST have a non-empty GitHub Issue title;
- MUST have a non-empty Markdown body;
- MAY override `slug`, `description`, and `created_date` independently;
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
- MAY override `description` and `created_date` independently;
- MAY use `tag:*` labels without contributing to the Blog Tags taxonomy;
- enters `/ideas/` and sitemap;
- does not enter Blog, Blog Tags, or `/atom.xml`;
- uses `/ideas/{issue_number}/` as its canonical path;
- uses its title as a concise summary and its Markdown body as the Idea content;
- binds comments to its own Issue number.

### 7.3 About

Site configuration MAY select an About Issue by immutable `about.issue_number`.
Without an explicit selection, the compiler selects the sole valid, published,
allowed-author About Issue. If none exists, the site displays Profile About,
not invented Issue Content.

An About Issue:

- MUST match `about.issue_number` when explicitly configured;
- MUST have `type:about` and `published`;
- MUST have a non-empty GitHub Issue title and Markdown body;
- MUST NOT provide `slug`;
- MAY override `description` and `created_date` independently;
- MUST NOT use `tag:*`;
- uses `/about/` as its canonical path;
- does not enter Blog, Ideas, Blog Tags, or `/atom.xml`;
- binds comments to its own Issue number.

An explicit selection has priority over discovery and Profile About. If the
selected Issue is missing, is a Pull Request, is unauthorized, lacks `published`,
has the wrong type, or fails validation, the build MUST fail rather than fall
back. More than one published, allowed-author `type:about` Issue remains a
validation error; the compiler MUST NOT silently pick the newest.

Profile About has no Issue number, authored date, or comment thread and MUST NOT
be represented as a fabricated Article or Issue. Failure to fetch necessary
Issue inputs MUST NOT be misreported as an empty set eligible for fallback.

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
- Display MAY use the configured site timezone.
- Blog and Idea pages display `created_date`; About MUST NOT display it.
- An Atom entry `published` value uses the Issue `created_at` timestamp.
- An Atom entry `updated` value uses the GitHub Issue `updated_at` value.
- The Atom feed `updated` value uses the maximum `updated_at` among its entries.
- When the Blog collection is empty, the compiler still generates a valid empty
  feed and uses the build start time as its feed-level `updated` value.
- The `published` label, not a future timestamp, is the only publication gate.

## 9. Rendering and security

- Markdown MUST be rendered as GitHub-Flavored Markdown or a documented,
  compatible subset.
- Raw HTML MUST be sanitized with an allowlist after Markdown rendering.
- Scripts, event-handler attributes, dangerous URL schemes, and unsafe embeds
  MUST be removed or rejected.
- Jinja/template autoescape does not replace Markdown sanitization.
- Front matter MUST NOT enable arbitrary template selection, code execution,
  script injection, or per-content plugins in v1.

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

Profile About and Projects have no Issue comment thread.

## 11. Route integrity

The compiler MUST build one global route registry before writing output and
reject:

- duplicate canonical paths;
- duplicate slugs;
- malformed tag keys;
- reserved-route collisions.

Blog tags use `/tags/` for the index and `/tags/{tag}/` for tag archives.
Canonical routes MUST use lower-case ASCII route keys and a trailing `/`.
Canonical paths MUST be converted to Unicode NFC before validation. Collision
checks MUST additionally compare case-folded paths so local case-insensitive
filesystems and GitHub Pages cannot produce divergent output.
The complete reserved-route set comes from all pages registered for the site,
not from a separate hard-coded Issue list.

Canonical links, internal links, sitemap entries, feed URLs, Open Graph URLs,
and output filesystem paths MUST be produced from that same route registry.
Every validation error SHOULD include a stable error code and Issue number when
an Issue caused the error. The compiler MUST collect and report all detectable
content validation errors in one run before failing the build.

## 12. Single current format

The Site Compiler supports only the current Issue Content Contract and performs
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
