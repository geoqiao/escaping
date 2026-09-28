---
status: accepted
amends: ADR-0007 (a Theme came only from escaping or the site repository) and
  ADR-0008 (extends named only a built-in Theme; loading never used the network)
---

# Themes from GitHub repositories

Until 0.3.0 a site could use Quiet or a folder in its own repository. Using
someone else's Theme meant copying it, and updating meant replacing the copy
by hand, so a Theme had no way to reach other sites and no way to be updated.
One repository per Theme would also have wasted repositories for authors with
several small Themes.

## Decision

**A Theme can be a folder of a public GitHub repository at a version:**
`github.com/OWNER/REPOSITORY[/FOLDER]@VERSION`, in `theme.use` or `extends`.
The version (tag, branch or commit) is required, like `uses:` in a workflow.
One repository holds any number of Themes; a tag versions them all.

**Every build downloads it.** escaping fetches the repository archive at that
version from `codeload.github.com` without a token, unpacks only that folder
into a temporary directory and deletes it when the build ends. There is no
cache to go stale and no lock file: the address in `config.yaml` is the pin.
The download happens with the other Theme checks, before the token is used
and before any output is replaced; a failed download fails the build like any
other Theme error.

**Templates run in Jinja's sandbox.** A Theme from someone else runs in a
build that holds a token. The sandbox keeps templates away from Python
internals, files and environment variables. A Theme's HTML and JavaScript
still reach readers, so the docs recommend reading a Theme and pinning
unknown authors to a commit SHA.

**The list of Themes is a document**, [docs/themes/catalog.md](../themes/catalog.md),
changed by pull request. It links to the Themes; their code stays in their
authors' repositories.

## Consequences

A build needs to reach GitHub for a GitHub Theme, which it already needs for
Issues. Private Theme repositories are not supported. A tag or branch can be
moved by its author; only a commit SHA is fixed. Local folders and Quiet work
as before.
