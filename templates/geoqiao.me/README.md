# geoqiao.me theme

The production theme uses the A2 Quiet Ledger direction: neutral light and dark
surfaces, a restrained Coral accent, Songti display type, system sans prose,
and mono metadata. Home pairs a compact Issue timeline with a right-side
profile rail on desktop; content pages use a quiet single-column hierarchy.

This is a first-party theme maintained directly in `templates/geoqiao.me/`.
It renders the complete strict SiteModel: Home, Blog archive/detail/pagination,
Ideas, About, Projects, Tags, and shared Utterances comments.

`_comments.html` keeps Issue-number bindings, `theme_mode: auto`
synchronization through `postMessage` and `MutationObserver`, and the Safari
lazy-iframe workaround.
