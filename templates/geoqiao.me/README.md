# geoqiao.me theme

The v1 production theme applies the approved Escape2 terminal visual language:
dark Nord surfaces, `#80AADD` accent, JetBrains Mono for headings/code, Source
Sans 3 for prose, a 760px reading shell, visible focus states, mobile-first
content order, and reduced-motion support.

The declarative theme contract is resolved from `theme.yaml`. It renders the
full strict SiteModel: Home, Blog archive/detail/pagination, Ideas, About,
Projects, Tags, and shared Utterances comments. It never constructs URLs from
titles or Issue objects; pages receive pre-computed RouteRegistry values.

`_comments.html` keeps Issue-number bindings, `theme_mode: auto` synchronization
through `postMessage` and `MutationObserver`, and the Safari lazy-iframe
workaround.
