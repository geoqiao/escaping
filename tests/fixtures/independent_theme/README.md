# Independent Theme fixture

A small local Theme written only against the public Theme API 4 contract
(no `extends`), used by the theme contract, integration, browser and wheel
consumer tests.

- `theme.yaml` declares two options (`footer_note`, `comments_theme`) and
  English/Chinese UI strings.
- Templates read only `site`, `page`, `theme` and `t`; `404.html` is optional
  and has no canonical URL.
- Navigation is always visible and iterates `site.navigation` without adding
  entries.
- `about.html` branches on `page.item.is_profile`; Idea tags render as names.
- Comment markup is conditional and loads the shared
  `/assets/escaping/comments.js` only for Issue-backed pages.
- `static/css/style.css` provides system-font light/dark styling, focus
  states, wrapped navigation and a keyboard-focusable overflow region.
