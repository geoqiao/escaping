# Escaping Content Publishing

This context describes how authored content becomes Markdown files for a site, while keeping authoring, export, rendering and deployment responsibilities separate.

## Language

**Issue Content**:
A GitHub Issue whose native fields, labels, and body conform to the current content contract; once created, it is the sole authoritative representation of that content.
_Avoid_: Post issue, CMS record

**Issue Content Contract**:
The single current agreement that defines how Issue Content represents identity, type, publication state, metadata, and body content.
_Avoid_: Front matter format, Local Draft Contract

**Local Draft Contract**:
The single current input agreement shared by Local Draft Lint and the Issue Draft Uploader; it describes one-time creation input rather than authoritative Issue Content.
_Avoid_: Issue Content Contract, sync format, sidecar format

**Issue Draft Uploader**:
An optional one-way authoring tool that transforms a Local Draft into newly created Issue Content, unpublished unless the user explicitly authorizes publishing it; it does not update or synchronize Issue Content.
_Avoid_: Issue Publisher, sync command, build command

**Local Draft**:
A local Markdown document used only as input when creating Issue Content; after creation it has no synchronization or authority role.
_Avoid_: Source post, local canonical, working copy

**Local Draft Lint**:
Optional, read-only authoring assistance for a Local Draft; it is neither publication approval nor proof of future author eligibility or collection-wide slug uniqueness.
_Avoid_: Publishing gate, Issue validator, upload command

**Content Export**:
The published Issue Content written as Markdown files and a manifest. It is the only output of `escaping`: it has no pages, addresses or look.
_Avoid_: Sync, backup, Markdown source, build

**Content Export Contract**:
The single current agreement that defines the exported files, their front matter and the manifest. It is distinct from the Issue Content Contract, which defines what an author writes, and it is the only thing a Theme depends on.
_Avoid_: Issue Content Contract, front matter format, Theme API

**Config**:
The three sections of a site's `config.yaml` that `escaping` reads: `github`, `about` and `security`. Every other section of the file belongs to the site.
_Avoid_: Site Config, generator settings

**Site**:
The repository-owned code that reads a Content Export and makes a website: pages, addresses, feeds, rendering and its safety. `escaping` has no part in it.
_Avoid_: Site Compiler, generator output

**Theme**:
The look of a Site, which is site code that reads the Content Export. There is no separate Theme contract and nothing of a Theme is in `escaping`.
_Avoid_: Jinja Theme, Theme API, built-in Theme

**Template Repository**:
`escaping-template`: a complete Site with the default Theme and its workflows, copied by a new user. After the copy the user owns that code.
_Avoid_: Starter, built-in Theme

**Skipped Issue**:
Published Issue Content whose own content is invalid. It is left out of one export and reported by Issue number while the rest is exported.
_Avoid_: Draft, unpublished Issue

**Site Orchestrator**:
The site-repository automation that prepares publishing labels, reacts to Issue events, runs the export at a pinned `escaping-site` version, and builds and deploys the Site. It changes version only when the site edits that pin.
_Avoid_: escaping daemon, watcher

**Published Content**:
Issue Content from an allowed author that carries the `published` label and satisfies exactly one supported content-type profile.
_Avoid_: Open issue, closed issue

**Content Type**:
The single semantic role assigned to Issue Content, currently Blog, Idea, or About.
_Avoid_: Category, tag

**Blog Tag**:
A classification of Blog content that a Site may collect in a tag archive.
_Avoid_: Idea Tag

**Idea Tag**:
A display-only classification of Idea content; it does not join a Blog tag archive.
_Avoid_: Blog Tag, Idea tag archive
