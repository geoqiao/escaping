# geoqiao.me visual baseline

## Decision

`geoqiao.me` uses the approved A2 Quiet Ledger direction as its production
baseline and the generator's default built-in Theme. It is maintained as a
package resource in `src/github_blog/themes/geoqiao.me/`; consumers receive it
inside the wheel and may choose a Config-relative local Theme instead.

## Visual system

- **Palette:** neutral light/dark surfaces with Coral `#c4483a` in light mode
  and `#ff7768` in dark mode.
- **Typography:** restrained Songti display type, system sans prose, and system
  mono metadata.
- **Home:** the approved two-line opera quotation, a compact Issue timeline,
  and a right-side profile rail on desktop. Mobile hides the profile rail and
  leads with content.
- **Content:** Blog, Ideas, Projects, Tags, and About use a quiet single-column
  hierarchy without boxed cards or decorative row separators.
- **Signature:** real GitHub Issue identity, a Coral marker, and a thin vertical
  trace.
- **Comments:** the Theme declares only its container/default color mode; the
  generator-owned shared `comments.js` binds Issue-number Utterances, follows
  `data-theme`, and preserves the Safari lazy-iframe workaround.

## Accessibility and responsive requirements

- Keyboard focus remains visible and navigation remains keyboard operable.
- Light and dark mode are system-aware and reload-stable.
- Code and tables contain horizontal overflow locally; the page itself must not
  scroll horizontally.
- `prefers-reduced-motion: reduce` minimizes motion.
- Skip-to-content and meaningful control labels remain available.
