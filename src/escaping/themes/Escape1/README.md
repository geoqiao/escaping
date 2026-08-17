# Escape1 theme

Escape1 is the light/dark minimal theme. It consumes the same strict
SiteModel and RouteRegistry contract as Escape2 and geoqiao.me: Home, Blog,
Ideas, About, Projects, Tags, Atom metadata, and Issue-bound Utterances
comments are supplied as resolved models rather than raw Issues.

The generator-owned shared `comments.js` keeps automatic theme synchronization
and the Safari lazy-iframe workaround. Theme-specific styling may differ, but content rules,
canonical routes, sanitization, and empty states remain shared.

On small screens, the menu exposes its expanded state, closes with Escape from
inside the navigation, and restores focus to the menu toggle.

Mermaid 11.16.1 is vendored with its license under `static/vendor` and fetched
by the browser only when a Mermaid code block is present.
