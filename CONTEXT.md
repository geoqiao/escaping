# Escaping Content Publishing

This context describes how authored content becomes a static personal site while keeping authoring, compilation, and deployment responsibilities separate.

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
An optional one-way authoring tool that transforms a Local Draft into newly created, unpublished Issue Content; it does not publish, update, or synchronize Issue Content.
_Avoid_: Issue Publisher, sync command, build command

**Local Draft**:
A local Markdown document used only as input when creating Issue Content; after creation it has no synchronization or authority role.
_Avoid_: Source post, local canonical, working copy

**Local Draft Lint**:
Optional, read-only authoring assistance for a Local Draft; it is neither publication approval nor proof of future author eligibility or collection-wide route uniqueness.
_Avoid_: Publishing gate, Issue validator, upload command

**Site Compiler**:
The `escaping` capability that converts Issue Content and repository-owned site content into a validated static site.
_Avoid_: Issue monitor, Issue Draft Uploader

**Site Config**:
Repository-owned choices for one generated site, overriding missing-value defaults field by field. Relative filesystem paths belong to the Site Config directory, never to the caller's working directory.
_Avoid_: Generator Config, global settings

**Theme**:
A trusted presentation of the site's pages and content, selected independently from authoring and publication decisions.
_Avoid_: Publishing plugin, content source

**Theme API**:
The versioned compatibility agreement defining the page information, assets and presentation behavior a Theme can rely on. Its version is distinct from the Site Compiler's release identity.
_Avoid_: Visual style version, automatic compatibility adapter

**Built-in Theme**:
A Theme distributed with the Site Compiler. Quiet is the default; geoqiao.me, Escape1, and Escape2 are alternatives.
_Avoid_: Downloaded theme, compiler cache

**Site Orchestrator**:
The site-repository automation that prepares publishing labels, reacts to repository events, and builds and deploys the site. It selects a stable release or an explicit fixed version and fixes the actual Site Compiler identity for each build.
_Avoid_: escaping daemon, watcher, compiler workflow

**Published Content**:
Issue Content from an allowed author that carries the `published` label and satisfies exactly one supported content-type profile.
_Avoid_: Open issue, closed issue

**Content Type**:
The single semantic role assigned to Issue Content, currently Blog, Idea, or About.
_Avoid_: Category, tag

**Blog Tag**:
A classification of Blog content whose published members are collected in a tag archive.
_Avoid_: Idea Tag

**Idea Tag**:
A display-only classification of Idea content; it neither creates nor joins a Blog tag archive.
_Avoid_: Blog Tag, Idea tag archive

**Project Catalog Entry**:
A repository-owned, curated description of a project displayed by the personal site.
_Avoid_: Project issue, repository mirror

**Site Profile**:
The site's structured identity and presentation data, supplied by repository-owned choices with missing values drawn from public GitHub profile data. It is distinct from an author's About Issue narrative.
_Avoid_: About Issue metadata

**Profile About**:
An About page presenting profile information when no About Issue is selected. It is not Issue Content and has no Issue identity or discussion thread.
_Avoid_: Placeholder Issue, generated About Issue

**Site Thesis**:
A repository-owned statement arranged in one or more deliberate lines and made available as an optional Theme presentation hint; configuring it does not require a Theme to place slogan copy on Home.
_Avoid_: Theme copy, Site Profile bio, hero placeholder
