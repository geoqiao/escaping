# 25 — Implement the approved A2 Quiet Ledger theme

**What to build:** Replace the site-owned `geoqiao.me` presentation override with the approved A2 Quiet Ledger direction while preserving the locked theme contract, routes, content semantics, comments behavior, and accessibility boundaries.

**Blocked by:** 12 — Resolve locked themes and site overrides; 15–17 — Complete the production geoqiao.me theme.

**Status:** implemented

- [x] Implement A2 directly as the first-party `templates/geoqiao.me/` theme; remove the unnecessary production lock and override layer.
- [x] Home uses the approved two-line opera quotation, a quiet Issue timeline, and the full A profile rail on the right at desktop widths.
- [x] Blog and tag archives expose real Issue identity, dates, titles, and plain tags without decorative row separators or boxed cards.
- [x] Blog/Idea detail, Ideas, Projects, Tags, and About use the same neutral + Coral system and content-first single-column hierarchy.
- [x] Light/Dark mode is keyboard operable, reload-stable, system-aware, and continues driving Utterances `theme_mode: auto` through `data-theme`.
- [x] Existing Safari Utterances compatibility, Issue-number comment binding, canonical routes, SEO metadata, overflow containment, focus visibility, and reduced-motion behavior remain intact.
- [x] Complete generated artifacts pass validation and representative desktop/mobile browser smoke without horizontal overflow.

## Approved visual decision

- **Direction:** A2 — Quiet Ledger / 安静台账.
- **Hero:** `演悲欢离合,当代岂无前代事?` / `观抑扬褒贬,座中常有剧中人。`
- **Signature:** real GitHub Issue number + Coral signal marker + very thin vertical trace.
- **Palette:** neutral light/dark surfaces with Coral `#c4483a` (light) and `#ff7768` (dark).
- **Typography:** restrained Songti display, system sans body, system mono metadata.
- **Desktop Home:** content on the left; A-style Profile rail on the right.
- **Mobile:** hide the Profile rail and lead directly into content.

## Test seams

The repository already accepts these public seams in `spec.md` and `docs/agents/testing.md`:

1. validated `BlogPost` values → immutable Home/archive/tag entry models carrying the Issue identity needed by the approved visual signature;
2. stable page models + shared context → rendered theme HTML;
3. complete generated files → `SiteArtifactValidator` and desktop/mobile browser behavior.

## Comments

The site owner approved A2 after reviewing the live prototype at `?variant=quiet-ledger`. This explicit decision supersedes the earlier Escape2-only visual baseline. During implementation, the owner also chose to simplify `geoqiao.me` into a directly maintained first-party theme instead of retaining a same-repository lock and near-complete override layer.

## Implementation record

- Added real Issue identity to Home, Blog archive, and tag archive entry models.
- Replaced every `geoqiao.me` page with the A2 shell and shared visual system.
- Kept the tests deliberately light: existing generic contracts plus one A2 identity smoke test.
- Verified 209 tests, Ruff, ty, complete artifact validation, theme persistence, comments binding, and browser overflow checks.
