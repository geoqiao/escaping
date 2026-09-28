# Extends Theme fixture

A local Theme that extends the built-in Quiet, used by the theme contract tests.

- `home-intro.html` and `head-extra.html` replace Quiet's partials of the same
  name; every other template comes from Quiet.
- `theme.yaml` adds the `now_text` option, a `/now/` page, one
  `/projects/{slug}/` page per configured project, and overrides one of
  Quiet's strings (`footer_thanks`).
- `project.html` extends `@quiet/base.html`, Quiet's own base template.
- `static/css/extra.css` is published at `/assets/css/extra.css` next to
  Quiet's files.
