# Local Draft Contract v1

Status: **Accepted**

## 1. Purpose and scope

This contract defines the local Markdown input accepted by the Issue Draft
Uploader. The uploader transforms one Local Draft into one newly created,
unpublished GitHub Issue that conforms to the
[Issue Content Contract](./issue-content-v1.md).

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY**
are normative requirements.

A Local Draft is one-time creation input. After successful Issue creation, the
Issue is the sole authoritative representation. The uploader MUST NOT bind the
file to the Issue, persist upload or synchronization state, or use the file to
update an existing Issue.

This contract does not define:

- post-creation editing or publication;
- synchronization, conflict resolution, or remote-to-local conversion;
- sidecar state;
- Site Compiler behavior beyond the referenced Issue Content Contract.

## 2. Document envelope

A Local Draft is a Markdown document with YAML front matter followed by a
Markdown body. Neither the Local Draft nor the generated Issue contains a
runtime schema or version field. The uploader and Site Compiler support one
current contract only.

## 3. Authored fields

The only allowed front matter fields are `title`, `type`, `slug`, `description`,
`tags`, and `created_date`. Unknown fields MUST be rejected. No other metadata
fields are part of the Local Draft Contract v1.

### 3.1 `title`

`title` is required. It MUST be a scalar string and MUST be non-empty after
trimming. The uploader MUST use it as the GitHub Issue title and MUST NOT copy
it into the Issue body front matter.

The uploader MUST NOT infer a title from the filename or from a Markdown
heading. A heading in the Markdown body remains part of the body.

### 3.2 `type`

`type` is required and MUST be exactly one of `blog`, `idea`, or `about`. The
uploader MUST translate it into exactly one corresponding `type:blog`,
`type:idea`, or `type:about` label. It MUST NOT copy `type` into the Issue body
front matter.

### 3.3 `slug`

`slug` is optional when `type` is `blog` and forbidden when `type` is `idea` or
`about`. An explicit value MUST satisfy the syntax and length rules in
[Issue Content Contract section 6.3](./issue-content-v1.md#63-slug) and be copied
into the Issue body front matter.

When omitted, the uploader MUST leave it omitted: no Issue number exists yet,
so it MUST NOT guess a route from the title or filename. The Site Compiler later
derives the Blog slug from the created Issue number. Idea and About routes
continue to follow Issue identity and content type.

### 3.4 `description`

`description` is optional for Blog, Idea, and About. An explicit value MUST
satisfy the authored plain-text validation rules in
[Issue Content Contract section 6.4](./issue-content-v1.md#64-description) and be
copied into the Issue body front matter.

The uploader MUST leave a missing description omitted; the Site Compiler owns
the sanitized-body default. Invalid, null, or explicitly blank values MUST NOT
be treated as missing or silently replaced. Providing one metadata override
MUST NOT require the other optional overrides.

### 3.5 `tags`

`tags` is optional when `type` is `blog` or `idea` and forbidden when `type` is
`about`. When omitted for Blog or Idea, it defaults to an empty list. Each item
MUST be a tag key without the `tag:` prefix and MUST satisfy the syntax and length rules
in [Issue Content Contract section 4.3](./issue-content-v1.md#43-tag-labels).
Duplicate keys are forbidden.

The uploader MUST translate each key into one `tag:<key>` label and MUST NOT
copy `tags` into the Issue body front matter.

### 3.6 `created_date`

`created_date` is optional. An explicit original creation date MUST be a quoted,
valid `YYYY-MM-DD` string and be copied into the Issue body front matter. When
omitted, the uploader MUST NOT guess an Issue creation date from the local clock
or file timestamp; the Site Compiler later uses the Issue's UTC creation date.

The Site Compiler displays the resolved date for Blog and Idea, while sorting
both by the GitHub Issue `created_at` timestamp. About does not display a date.
The `published` label remains the publication gate.

### 3.7 Markdown body

The Markdown body after the closing front matter delimiter is required and MUST
be non-empty after trimming for Blog, Idea, and About. For Idea, `title` is a
concise summary rather than a substitute for body content.

The uploader MUST copy the Markdown body unchanged. It MUST NOT rewrite text,
headings, links, images, code blocks, or formatting.

## 4. Upload result

A successful upload MUST create a new Issue without the `published` label and
report its immutable Issue number and URL. Only explicitly supplied Issue body
metadata is emitted; when none is supplied, the Issue body MAY be plain Markdown
without an envelope. The uploader MUST NOT modify the Local Draft or create a
sidecar file.

Optional lint or attachment assistance is not an upload, publication approval,
or synchronization capability. It MUST NOT rewrite an existing published slug
or authorize committing attachments, pushing, or editing an existing Issue.
The Local Draft's `title` and `type` remain required because the new Issue needs
these native fields; optional metadata does not make an arbitrary Markdown file
an upload-ready Local Draft.
