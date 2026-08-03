# Reusable Site Generator Refactor

## Goal

Make `escaping` installable and reusable without depending on its checkout directory. The generator packages `geoqiao.me` as its default Theme; the site repository owns real configuration and production orchestration.

## Accepted direction

- The generator keeps `config.example.yaml`, the default packaged `geoqiao.me` Theme, and packaged Escape1/Escape2 alternatives.
- Built-in Themes are package resources.
- Local Theme and output paths are resolved from the Config directory, never implicit process CWD.
- `ThemeLoader` loads only declared local/package resources; Git/HTTP fetch and commit pinning belong to the Site Orchestrator.
- Route construction happens once through `RouteRegistry` and pages hold the resulting `Route`.
- The existing `SiteModelBuilder` becomes the deep model-building module; internal builders stop being public seams.
- Rendering data has one source in `SiteModel`; Theme loading remains an injected implementation dependency.
- Sanitization, output containment, atomic publication, `ContentCompiler`, `IssueSnapshot`, and artifact validation behavior remain protected.

## Confirmed test seams

1. `ThemeLoader`: a built-in Theme loads and copies assets outside the source checkout; a local Theme resolves from the Config root.
2. CLI/consumer: `blog-gen --config /path/config.yaml` behaves independently of CWD.
3. Installed wheel: a clean consumer can load a packaged reference Theme and compile representative Issue snapshots.
4. `RouteRegistry` / `SiteModelBuilder`: route, canonical URL, sitemap, and output mappings remain unchanged.
5. `SiteCompiler`: failed builds preserve old output; complete builds produce validated artifacts.

## Rollout constraint

The generator and site repositories cannot change atomically. Push the verified generator branch first, pin its full commit from a non-production site migration branch, verify the branch build, then request separate authorization for merge and Pages deployment.

## Out of scope until product decision

- Plugin/feature framework.
- Removing Ideas or Projects.
- Simplifying the HTML sanitizer or atomic output staging.
