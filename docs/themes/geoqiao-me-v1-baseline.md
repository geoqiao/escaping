# geoqiao.me v1 visual baseline

## Decision

`geoqiao.me` v1 adopts the current `Escape2` visual language as its production baseline. Ticket 13 remains `wontfix`: a disposable visual prototype is not required to gate this implementation. Broader visual exploration is deferred until the strict compiler and generated artifacts are stable.

## Visual system

- **Palette:** deep charcoal background, elevated charcoal header/cards, near-white text, muted gray secondary text, and cool blue `#80AADD` accent with a lighter hover state.
- **Typography:** `JetBrains Mono` for terminal identity, headings, metadata, and code; `Source Sans 3` for prose and controls. Fallbacks remain monospace and sans-serif system fonts.
- **Layout:** centered single-column content with a 760px maximum width; a compact terminal-style header; readable vertical rhythm; page-specific content stays in the shared shell.
- **Navigation:** terminal identity on the left and explicit text links on the right; mobile collapses to an accessible checkbox/menu control. Every link is supplied by the registered route/model contract.
- **Content:** Blog, Idea, About, and Projects use the same dark surface, blue links, compact metadata, readable prose, horizontal overflow for code/tables, and intentional empty states.
- **Code and media:** code uses the Nord-compatible dark code surface and horizontal scrolling; authored images remain responsive; long titles and prose wrap without changing route semantics.
- **Comments:** Issue-number-bound Utterances appears after authored content. `theme_mode: auto` follows `data-theme` through `postMessage` and `MutationObserver`; the Safari workaround removes `loading="lazy"` from injected iframes.

## Accessibility and responsive requirements

- Keyboard focus is visibly outlined with the accent color.
- Foreground/background contrast remains readable in the dark baseline.
- `prefers-reduced-motion: reduce` disables cursor and transition animation.
- The mobile order is identity → navigation → content → comments → footer; no essential content is hidden behind hover.
- Skip-to-content remains available in the shared shell.
- Images have meaningful alternative text; controls expose labels and expanded state.

## Scope boundary

The geoqiao.me theme is declarative and locked by a full commit/API-version record. Site-owned overrides take precedence over locked templates and assets. Adaptations from Escape2 are limited to the new content pages, strict routes, accessibility, and responsive correctness; this document does not authorize an unrelated redesign.
