# Remove legacy generator-owned site state and Theme fetching

Status: ready-for-human
Priority: P0
Blocked by: 04

## Outcome

After production cutover, retain only `config.example.yaml` and packaged reference Themes in the generator. Delete `theme_lock`, compiler fetch/cache/update paths, personal Config/Theme, and stale deployment assumptions.

## Acceptance

- No production path reads generator-root `config.yaml` or `templates/geoqiao.me`.
- Theme provenance is owned by the pinned generator/site workflow.
- README, AGENTS, Theme contract, and deployment documentation state current facts.

## Comments

Removed generator-owned production Config, top-level Themes, Theme lock/fetch/cache/update code, and the copied production workflow. `geoqiao.me` is now the packaged default Theme; the site migration branch owns the real Config.
