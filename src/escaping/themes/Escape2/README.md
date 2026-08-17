# Escape2 theme

Escape2 is the dark terminal visual baseline used by the v1 geoqiao.me theme:
Nord-inspired surfaces, cool blue accents, local system font stacks, responsive
navigation, visible focus, and reduced-motion support. It has no remote Webfont
dependency.

The declarative templates consume the strict SiteModel and RouteRegistry for
Home, Blog, Ideas, About, Projects, Tags, and Issue-bound Utterances comments.
The generator-owned shared `comments.js` preserves automatic theme
synchronization and the Safari iframe workaround.

On small screens, the menu exposes its expanded state, closes with Escape from
inside the navigation, and restores focus to the menu toggle.

Mermaid 11.16.1 is vendored with its license under `static/vendor` and fetched
by the browser only when a Mermaid code block is present.
