---
status: accepted
---

# Separate authoring, compilation, and orchestration

Local Draft uploading, static-site compilation, and event-driven deployment are separate responsibilities. An optional Issue Draft Uploader creates unpublished Issue Content from Local Drafts; `escaping` consumes the Issue Content Contract as a pure Site Compiler and never creates or edits Issues; GitHub Actions acts as the Site Orchestrator. This boundary preserves manual GitHub Issue editing, keeps `escaping` independently reusable, and prevents authoring behavior or deployment credentials from leaking into the compiler.
