# Remove dead runtime surface and consolidate verification/docs

Status: ready-for-human
Priority: P2
Blocked by: 07

## Outcome

Remove unused dependencies, scaffold/duplicate entry points, dead Markdown rendering, duplicate test owners, and stale historical documentation after current contracts have captured durable decisions.

## Acceptance

- Runtime dependency declarations match imports.
- Theme contract has one parameterized owner plus consumer/CLI tracers.
- Shared comments behavior is extracted only if its generator ownership and browser contract are explicit.
- Completed plans/research/tickets are deleted or archived after retained decisions are documented.

## Comments

Removed six unused runtime dependencies, scaffold/duplicate entry points, dead Markdown rendering, repeated builder/writer tests, historical plans/research, and stale deployment copies. Added one shared packaged `comments.js` and retained one parameterized Theme contract plus CLI/wheel tracers.
