# Package reference Themes and introduce ThemeLoader

Status: ready-for-human
Priority: P0

## Outcome

A single local declarative `ThemeLoader` loads either a packaged reference Theme or a Config-relative Theme. The installed wheel contains reference templates/assets. Compiler-side fetch/cache/update behavior is removed only after the consumer cutover.

## Acceptance

- Built-in Theme loading works after changing CWD away from the checkout.
- Theme manifest, API version, required template/asset validation, autoescape, and `StrictUndefined` remain enforced.
- Template and static assets come from the same loaded Theme.
- Wheel contents include reference Themes.

## Comments

Implemented packaged default `geoqiao.me` plus Escape1/Escape2 alternatives and a single manifest-validating `ThemeLoader` for built-in and Config-relative local Themes. A wheel-zip consumer builds a representative site outside the checkout and verifies shared comments assets. Legacy lock/fetch code was removed in Ticket 05.
