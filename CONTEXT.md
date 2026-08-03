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
The single current input agreement accepted by the Issue Draft Uploader; it describes one-time upload input rather than authoritative Issue Content.
_Avoid_: Issue Content Contract, sync format, sidecar format

**Issue Draft Uploader**:
An optional one-way authoring tool that transforms a Local Draft into newly created, unpublished Issue Content; it does not publish, update, or synchronize Issue Content.
_Avoid_: Issue Publisher, sync command, build command

**Local Draft**:
A local Markdown document used only as input when creating Issue Content; after creation it has no synchronization or authority role.
_Avoid_: Source post, local canonical, working copy

**Site Compiler**:
The `escaping` capability that converts Issue Content and repository-owned site content into a validated static site.
_Avoid_: Issue monitor, Issue Draft Uploader

**Site Config**:
Repository-owned configuration for one generated site. Relative filesystem paths are interpreted from the Site Config directory, never from the caller's working directory.
_Avoid_: Generator Config, global settings

**Built-in Theme**:
A manifest-validated Theme distributed as a Site Compiler package resource. `geoqiao.me` is the default; Escape1 and Escape2 are alternatives. Remote fetching and commit pinning are not ThemeLoader responsibilities.
_Avoid_: Downloaded theme, compiler cache

**Site Orchestrator**:
The site-repository automation layer that reacts to repository events, invokes a release/full-SHA-pinned Site Compiler with an explicit Site Config, and deploys its artifact.
_Avoid_: escaping daemon, watcher, compiler workflow

**Published Content**:
Issue Content from an allowed author that carries the `published` label and satisfies exactly one supported content-type profile.
_Avoid_: Open issue, closed issue

**Content Type**:
The single semantic role assigned to Issue Content, currently Blog, Idea, or About.
_Avoid_: Category, tag

**Project Catalog Entry**:
A repository-owned, curated description of a project displayed by the personal site.
_Avoid_: Project issue, repository mirror

**Site Profile**:
Repository-owned structured identity data shared by Home and site-wide presentation, currently an avatar, short bio, and links; the detailed About narrative belongs to About Issue Content.
_Avoid_: About page content, About Issue metadata
