---
status: accepted; amended by ADR-0012 and ADR-0013 (the export is now the only output)
amends: ADR-0001 (escaping's only product was a compiled static site)
---

# Content Export for sites built with another tool

Until now the only thing `escaping` produced was a finished site: HTML from
Jinja Themes. A site that wants components, client-side behavior or a host with
its own build had to give up Issues as its content source, although reading
Issues, the publication labels, the author list and the content rules have
nothing to do with how pages are drawn.

## Decision

**`escaping-site export` writes the published Issue Content as Markdown files.** One
file per Blog post, Idea and About Issue, with resolved front matter, and a
`manifest.json`; the files are defined by
[Content Export v1](../contracts/content-export-v1.md).

**Selection is the Content Compiler's.** The export runs the same compiler as
a build, so the same Issues are published, skipped or refused, with the same
diagnostics and exit status. There is one set of content rules, not two.

**The body is the author's Markdown, not sanitized HTML.** The consuming site
renders it and owns the safety of that rendering. Exporting HTML as well would
keep the sanitizer in charge, but it would also keep `escaping` in charge of
how content looks, which is what the export hands over.

**The export directory is published like a built site**: staged, swapped in by
rename, and marked with `.escaping-output`. It must not overlap
`paths.output`.

**The export is delivered as the `escaping-site` package on PyPI, not as a second
Action.** The existing Action exists because a build needs the Pages settings
of the repository; an export needs nothing from the platform, so an Action
would only wrap one command. A workflow runs `uvx escaping-site@X.Y.Z export`, and the same line works on a laptop. The existing Action is
unchanged.

## Consequences

Routes, feeds, the sitemap, search, redirects, Projects and comments belong to
the consuming site. Comments keep working because the exported
`issue_number` is the thread's identity.

An exporting site still reads the full Site Config, including fields that only
a Theme uses, and needs `github.repo` and `site.url` in it.
([ADR-0012](0012-one-content-core-two-outputs.md) ends this.)

The Site Compiler, the Theme API and Quiet stay as they are in this release.
Whether `escaping` later drops them and keeps only the content side is a
separate decision, to be taken after a real site has run on the export.
