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
An optional one-way authoring tool that transforms a Local Draft into newly created Issue Content, unpublished unless the user explicitly authorizes publishing it; it does not update or synchronize Issue Content.
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

**Content Export**:
The published Issue Content written as Markdown files and a manifest, for a site that another tool builds. It carries the same selection and content rules as the Site Compiler and no pages, routes or Theme.
_Avoid_: Sync, backup, Markdown source

**Content Export Contract**:
The single current agreement that defines the exported files, their front matter and the manifest; it is distinct from the Issue Content Contract, which defines what an author writes.
_Avoid_: Issue Content Contract, front matter format

**Site Config**:
Repository-owned choices for one generated site, overriding missing-value defaults field by field. Relative filesystem paths belong to the Site Config directory, never to the caller's working directory.
_Avoid_: Generator Config, global settings

**Theme**:
A trusted presentation of the site's pages and content, selected independently from authoring and publication decisions.
_Avoid_: Publishing plugin, content source

**Theme API**:
The versioned agreement between the Site Compiler and a Theme: the `theme.yaml` manifest, the four template names (`site`, `page`, `theme`, `t`), the template each page kind uses and its fallback, the `url` filter and the `/assets/` URL space. Its version is distinct from the Site Compiler's release identity.
_Avoid_: Visual style version, automatic compatibility adapter

**Built-in Theme**:
A Theme distributed with the Site Compiler. Quiet is the sole built-in and default Theme and uses the same Theme API as a local Theme, without special treatment.
_Avoid_: Downloaded theme, compiler cache

**GitHub Theme**:
A Theme in a folder (or at the root) of a public GitHub repository, named as `github.com/OWNER/REPOSITORY/FOLDER@VERSION` by `theme.use` or `extends`. Each build downloads that version without a token and deletes it afterwards; one repository may hold several Themes, and one tag versions all of them.
_Avoid_: Theme registry, theme package, installed theme

**Theme Option**:
A presentation choice declared with a type and default by a Theme's manifest and set by the site under `theme.options`. It has no meaning after switching to a Theme that does not declare it.
_Avoid_: Site setting, generator config

**Site Pages**:
The pages a site has, chosen in its Site Config under `pages`: each built-in section on, off or moved, plus extra pages at one fixed route or once per Project Catalog Entry, each rendered by a named Theme template. Routes are registered with the same registry as every other page.
_Avoid_: Theme page, plugin page

**Redirect**:
An old address of the site listed under `redirects` that sends visitors to a current page. A page always wins over a redirect.
_Avoid_: Alias, slug history

**Skipped Issue**:
Published Issue Content whose own content is invalid. It is left out of one build and reported by Issue number while the rest of the site is published.
_Avoid_: Draft, unpublished Issue

**Site Orchestrator**:
The site-repository automation that prepares publishing labels, reacts to repository events, and builds and deploys the site. It pins the Site Compiler by release tag or full commit SHA in `uses:` and calls the generator's reusable Action; it changes version only when the site edits that pin.
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
The site's structured identity data (avatar, bio, links), supplied by repository-owned choices with missing values drawn from public GitHub profile data. It is distinct from an author's About Issue narrative and from Theme Options.
_Avoid_: About Issue metadata

**Profile About**:
An About page presenting profile information when no About Issue is selected. It is not Issue Content and has no Issue identity or discussion thread.
_Avoid_: Placeholder Issue, generated About Issue
