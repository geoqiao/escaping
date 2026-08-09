# geoqiao.me Signal Blue visual baseline

## Decision

`geoqiao.me` uses the approved centered Signal Blue direction as its production
baseline and the generator's default built-in Theme. It is maintained as a
package resource in `src/escaping/themes/geoqiao.me/`; consumers receive it
inside the wheel and may choose a Config-relative local Theme instead.

## Visual system

- **Palette:** Snow `#f4f6f8`, white paper, Ink `#121826`, and Signal Blue
  `#315efb` in light mode; Night `#0c1118`, raised paper `#121925`, and Signal
  Blue `#83a0ff` in dark mode.
- **Typography:** Apple/system sans for display, prose, navigation, and metadata;
  code uses the local system monospace stack. The Theme has no Webfont loading
  dependency.
- **Header:** a blue identity rule and stacked `GEO QIAO` / `NOTES / TOOLS /
  LIFE` wordmark share the existing 72px Header with navigation.
- **Home:** the approved two-line opera quotation, a centered Issue timeline,
  and a right-side profile rail on desktop. Mobile hides the profile rail and
  leads with content.
- **Blog archive:** the current centered 900px shell and quiet ledger rows.
- **Blog article:** equal 96px metadata/outline rails around a centered 620px
  reading column. The outline is generated from rendered `h1`/`h2`/`h3` headings;
  side rails collapse below desktop widths.
- **Other content:** Ideas, Projects, Tags, and About retain a quiet
  single-column hierarchy without boxed cards or decorative row separators.
- **Comments:** the Theme declares only its container/default color mode; the
  generator-owned shared `comments.js` binds Issue-number Utterances, follows
  `data-theme`, and preserves the Safari lazy-iframe workaround.

## Accessibility and responsive requirements

- Keyboard focus remains visible and navigation remains keyboard operable.
- Blog remains the single current navigation item on both archive and detail
  pages.
- Light and dark mode are system-aware and reload-stable.
- Code and tables contain horizontal overflow locally; the page itself must not
  scroll horizontally.
- Article side rails collapse before they can reduce the reading column below a
  comfortable width.
- `prefers-reduced-motion: reduce` minimizes motion.
- Skip-to-content and meaningful control labels remain available.
