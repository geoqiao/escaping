# Deepen SiteModelBuilder and remove rendering data duplication

Status: ready-for-human
Priority: P1
Blocked by: 06

## Outcome

Make the existing `SiteModelBuilder` the external model-building seam, internalize one-caller builders, add `SiteMetadata`, and make renderer/validator obtain render facts from `SiteModel` rather than a second Settings source.

## Acceptance

- Home/Archive/Tags/Atom builders are internal implementation, not extra external seams.
- Test-only writer functions are gone.
- Site identity/profile/navigation/comments/asset metadata have one model source.
- Renderer receives a loaded Theme dependency but reads no render data from Settings.
- Artifact validator remains a deep module and preserves all safety checks.

## Comments

Introduced the single public `SiteBuilder`, internalized Home/archive/tag/Atom builders, removed test-only writers, and added `SiteMetadata`. Renderer and artifact validator now consume `SiteModel`, not Settings.
