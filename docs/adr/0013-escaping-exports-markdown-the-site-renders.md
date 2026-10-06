---
status: accepted
supersedes: ADR-0007, ADR-0008, ADR-0009, ADR-0010, ADR-0012
amends: ADR-0001, ADR-0011
---

# escaping exports Markdown; the site renders it

ADR-0012 kept two products: a finished site made with Jinja Themes, and the
content alone for a site built elsewhere. That left two ways to write a theme,
with two contracts. The built-in Theme used the internal models, so nothing
proved every day that the export was enough to build a site. And the author's
own site had moved to the export, so the Theme path had no real user left.

## Decision

**`escaping` has one output: the Content Export.** It selects Issues, applies
the content rules, resolves every value and writes Markdown files and a
manifest. `escaping-site export` is the only command.

**Everything about a website left the package**: Theme API 4, Quiet, GitHub
Themes, routes, pagination, the Atom feed, the sitemap, the search index,
redirects, Projects, artifact validation, the Action and the starter.

**The default look is a site in the template repository.** It reads the
export, exactly like a site an author writes. A theme is site code that reads
[Content Export v1](../contracts/content-export-v1.md); there is no second
theme contract.

**The Config is three sections**: `github`, `about` and `security`. Every other
section of the file is the site's and is neither read nor checked. Site
settings such as the title are written by the user in the site; `escaping` no
longer reads a GitHub profile or the Pages address to fill them in.

## Consequences

A site made from the template owns a copy of the theme code. A fix to the
template's theme does not reach existing sites; the content side still
upgrades by changing one version number.

Sites on 0.5 keep working while their workflow stays on the `v0.5.1` tag. They
cannot move to 0.6.0 without changing how the site is built.

Rendering, sanitizing raw HTML, addresses and feeds are the site's
responsibility. `escaping` still renders and sanitizes each body while it
exports, only to refuse a body that cannot be rendered and to derive the
default description.

`escaping-themes` has no further use for 0.6.0 and later.
