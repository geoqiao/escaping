# Independent Theme fixture

This fixture is a small API 2 local Theme written against the public Theme authoring contract.

- `theme.yaml` declares the complete ten-template API 2 surface and local asset directories.
- Navigation is always visible and iterates `navigation_items` without adding entries.
- `about.html` branches on `about_is_profile`; Idea tags render as names only.
- Comment markup is conditional and loads the compiler-owned `comments.js` path only for Issue-backed pages.
- `static/css/style.css` provides system-font light/dark styling, focus states, wrapped navigation, and a keyboard-focusable rich-content overflow region.
