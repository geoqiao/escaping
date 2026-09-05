# Third-party components

Escaping's own license remains MIT; this does not describe every dependency's license.

## HTML sanitization dependency

`escpe` declares **nh3 0.3.7** as a separate PyPI runtime dependency. It does not vendor
nh3's native binaries into the escaping wheel or generated static site.

| Component | License / source entry |
| --- | --- |
| [nh3 0.3.7](https://pypi.org/project/nh3/0.3.7/#files) | MIT; source archive includes Cargo.toml and Cargo.lock |
| [Ammonia 4.1.4](https://crates.io/crates/ammonia/4.1.4), [html5ever 0.39.0](https://crates.io/crates/html5ever/0.39.0) | MIT OR Apache-2.0 |
| [cssparser 0.37.0](https://crates.io/crates/cssparser/0.37.0), [dtoa-short 0.3.5](https://crates.io/crates/dtoa-short/0.3.5) | MPL-2.0 |

nh3's native dependency lock also includes Unicode-3.0 and
Apache-2.0 WITH LLVM-exception components. The table is not an exhaustive license
inventory; consult the pinned source lock and each upstream distribution's notices.

If we later distribute a bundled executable, native binaries, a container image or
modified third-party source, review the actual bundle's licenses, notices and source
availability obligations (including MPL-2.0) before release. Separate dependency
installation is not a blanket conclusion that downstream obligations cannot apply.

## Existing browser assets

The vendored Mermaid bundle retains its LICENSE, README and bundled third-party
notices under `src/escaping/static/vendor/mermaid-11.16.1/`. Quiet's Manrope and Source
Serif 4 fonts retain their SIL Open Font License texts under
`src/escaping/themes/Quiet/static/fonts/`. These notices remain included with the assets.
