# geoqiao.github.io strict Issue audit and migration record

Date: 2026-08-02
Repository: `geoqiao/geoqiao.github.io`
Compiler branch: `feature/geoqiao-personal-site-v1`

## Read-only audit before migration

The public Issue snapshot contained 40 Issue records. The intended historical
Blog set was the 34 Issues carrying the legacy `blog` label. Those 34 Issues
had no strict `type:*`/`published` labels and no Issue Content v1 front matter.
The configured About selection was Issue #1, but #1 was a legacy Blog Issue and
was not a valid published About Issue.

Six records had no legacy `blog` label and were not classified automatically:
#22, #33, #37, #38, #39, and #40. The site owner chose to remove those Issues;
no compiler migration changed their content.

The audit was read-only and checked the fields needed by the accepted contract:
labels, author, publication state, front matter, body presence, dates, slug
requirements, tags, About singleton selection, and route uniqueness.

## Migration actions

- Created Issue #42, titled `关于我`, from the configured Site Profile bio.
- Added `type:about` and `published` to #42; it has no tags or slug.
- Set `config.yaml:about.issue_number` to `42`.
- Migrated the 34 legacy Blog Issues.
- Added `type:blog`, `published`, and normalized `tag:*` labels.
- Added valid `slug`, `description`, and quoted `created_date` front matter.
- Kept the original Markdown body byte-for-byte after the closing front matter
  delimiter. No Issue was deleted by the compiler migration.

## Post-migration verification

A fresh `ContentCompiler` snapshot contains:

- 34 valid published Blog posts;
- 0 Ideas;
- exactly one valid About page: Issue #42;
- no blocking diagnostics.

`GITHUB_TOKEN="$(gh auth token)" uv run blog-gen` completed successfully and
produced a validated real-data artifact with 68 HTML files and 75 total output
files. The artifact contains valid Atom and sitemap XML, canonical metadata,
Issue-number comments, no visible front matter, and no legacy `.html` routes.
