# geoqiao.me visual baseline

## Decision

`geoqiao.me` uses the approved A2 Quiet Ledger direction as its production
baseline. It is a first-party theme maintained directly in
`templates/geoqiao.me/`; site-specific changes do not require a lock or an
override layer.

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
- **Comments:** Issue-number-bound Utterances follows `data-theme`; the Safari
  lazy-iframe workaround remains intact.

## Accessibility and responsive requirements

- Keyboard focus remains visible and navigation remains keyboard operable.
- Light and dark mode are system-aware and reload-stable.
- Code and tables contain horizontal overflow locally; the page itself must not
  scroll horizontally.
- `prefers-reduced-motion: reduce` minimizes motion.
- Skip-to-content and meaningful control labels remain available.
