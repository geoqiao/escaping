# Resolve runtime paths from Config and trace the real CLI

Status: ready-for-human
Priority: P0
Blocked by: 01

## Outcome

The CLI explicitly derives a Config root and passes it through compilation. Output and local Theme paths no longer depend on process CWD. A real CLI tracer and an installed-wheel consumer tracer cover this behavior.

## Acceptance

- Absolute `--config` works from an unrelated CWD.
- Output containment uses the Config root.
- Local Theme paths use the Config root.
- `cli.py` is exercised through its public entry point.

## Comments

`SiteCompiler` now requires an absolute Config root; output containment and local Theme loading use it. CLI normalizes the explicit Config path, and tracers run from an unrelated CWD. Installed-wheel generation is covered by `tests/test_package_consumer.py`.
