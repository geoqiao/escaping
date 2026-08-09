# geoqiao.me Theme

The default built-in Theme uses the approved centered Signal Blue direction:
neutral light and dark surfaces, Signal Blue `#315efb` / `#83a0ff` accents,
and an Apple/system sans stack for display, prose, navigation, and metadata.
Code keeps a local system monospace stack and the Theme has no Webfont
dependency.

Home retains the centered Issue timeline and right-side profile rail on desktop.
Blog archives use the same quiet ledger rows. Blog articles use a centered
three-column composition with immutable Issue metadata, a 620px reading column,
and a generated section outline; the side rails collapse below desktop widths.
The Header uses the `GEO QIAO` / `NOTES / TOOLS / LIFE` wordmark with a Signal
Blue identity rule.

The Theme is distributed in the `escaping` wheel and renders the complete strict
SiteModel: Home, Blog archive/detail/pagination, Ideas, About, Projects, and
Tags. `_comments.html` owns only the comments container and Theme default; the
generator-owned shared `comments.js` provides Issue-number binding, automatic
theme synchronization, message validation, and the Safari lazy-iframe
workaround.
