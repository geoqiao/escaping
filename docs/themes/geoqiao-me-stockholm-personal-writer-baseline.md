# geoqiao.me Stockholm / personal-writer visual baseline

## Decision

The current default built-in Theme is the Stockholm / personal-writer direction: a quiet
editorial system for Chinese-first personal writing, tools, and life notes. It is maintained
as the package resource at src/escaping/themes/geoqiao.me/; consumers may choose Escape1,
Escape2, or a Config-relative local Theme instead.

This document records the Theme visual and interaction baseline, not compiler, route, Config,
or deployment architecture. Those boundaries remain in the Site Compiler contracts and ADRs.

## Visual direction

- **Surface and color:** generous neutral light surfaces and deep-plum dark surfaces, with the
  magenta-and-mint GQ mark as the signature accent. The CSS owns the actual tokens; the
  palette is not a compatibility contract.
- **Type:** local system sans for display, prose, navigation, and metadata, with a local
  system monospace stack for code. The Theme has no remote Webfont dependency.
- **Header:** a compact author mark and author name, primary navigation, and an explicit
  light/dark control form a restrained editorial header.
- **Home:** the newest Blog entry leads with its Issue identity and writing description;
  the author mark provides the visual counterweight. Recent writing follows as borderless
  editorial rows. Profile and About narrative remain on their own pages.
- **Indexes:** Blog, Ideas, and tag archives share an editorial index grammar rather than
  card grids or dense dividers. Blog archive pagination remains an archive concern.
- **Details:** Blog and Idea pages pair immutable Issue metadata with a comfortable reading
  column and a generated section outline on wide screens. The outline and metadata rail
  collapse into a single flow when space is limited.
- **Other pages:** Projects use numbered work rows, Tags use a subject matrix, and About
  uses the same author-mark and long-form reading language.
- **Comments:** the Theme owns only the comments container and default mode. The shared
  generator-owned comments.js provides immutable Issue-number binding, automatic theme
  synchronization, message validation, and the Safari lazy-iframe workaround.

## Accessibility, responsive, and motion contracts

These are durable behavior contracts even when the visual styling evolves:

- Keyboard focus remains visible; primary navigation, the mobile menu, theme control,
  article outline, and other controls remain keyboard operable.
- The skip-to-content link and meaningful control labels remain available. The mobile
  navigation exposes its expanded state, can be closed with Escape, and does not leave
  background content interactive while open.
- Light and dark mode follows the operating-system preference on first visit, while an
  explicit visitor choice remains stable across reloads.
- Blog remains the single current navigation item on both archive and detail pages.
- Code blocks and tables contain horizontal overflow locally; the page itself must not
  scroll horizontally.
- Article metadata and outline rails collapse before they make the reading column
  uncomfortably narrow.
- prefers-reduced-motion: reduce disables smooth scrolling and minimizes transitions
  and other motion.

## Intentionally not fixed here

Exact color values, font sizes, container widths, breakpoints, spacing, cache-busting
versions, and transition durations are CSS/template implementation details. They may change
with a visual refinement without changing this baseline or the Site Compiler architecture.
