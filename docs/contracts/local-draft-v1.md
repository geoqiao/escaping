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

`slug` is required when `type` is `blog` and forbidden when `type` is `idea` or
`about`. It MUST satisfy the syntax and length rules in
[Issue Content Contract section 6.3](./issue-content-v1.md#63-slug). The uploader
MUST copy it into the Issue body front matter, where the Site Compiler uses it
to derive `/blog/{slug}/`.

Idea and About routes are derived from Issue identity and content type, not from
a Local Draft slug.

### 3.4 `description`

`description` is required for Blog, Idea, and About. It MUST satisfy the
plain-text validation rules in
[Issue Content Contract section 6.4](./issue-content-v1.md#64-description). The
uploader MUST copy it into the Issue body front matter.

The uploader MUST NOT derive a missing description from the Markdown body.

### 3.5 `tags`

`tags` is optional when `type` is `blog` or `idea` and forbidden when `type` is
`about`. When omitted for Blog or Idea, it defaults to an empty list. Each item
MUST be a tag key without the `tag:` prefix and MUST satisfy the syntax and length rules
in [Issue Content Contract section 4.3](./issue-content-v1.md#43-tag-labels).
Duplicate keys are forbidden.

The uploader MUST translate each key into one `tag:<key>` label and MUST NOT
copy `tags` into the Issue body front matter.

### 3.6 `created_date`

`created_date` is required. It records when the Local Draft was actually
created, not when its GitHub Issue was created. It MUST be a quoted string in
`YYYY-MM-DD` format. The uploader MUST copy it into the Issue body front matter.

The Site Compiler displays `created_date` for Blog and Idea, while sorting both
by the GitHub Issue `created_at` publication timestamp. About retains the field
but does not display a date. The `published` label only controls whether the
content appears on the site.

### 3.7 Markdown body

The Markdown body after the closing front matter delimiter is required and MUST
be non-empty after trimming for Blog, Idea, and About. For Idea, `title` is a
concise summary rather than a substitute for body content.

The uploader MUST copy the Markdown body unchanged. It MUST NOT rewrite text,
headings, links, images, code blocks, or formatting.

## 4. Upload result

A successful upload MUST create a new Issue without the `published` label and
report its immutable Issue number and URL. The uploader MUST NOT modify the
Local Draft or create a sidecar file.
