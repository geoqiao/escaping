---
status: accepted; amended by ADR-0011 and ADR-0013 (compilation now ends at Markdown files)
---

# Separate authoring, compilation, and orchestration

Local Draft uploading, static-site compilation, and event-driven deployment are separate responsibilities. An optional Issue Draft Uploader creates new Issue Content from Local Drafts, published only when the user explicitly authorizes it; `escaping` consumes the Issue Content Contract as a pure Site Compiler and never creates or edits Issues; GitHub Actions acts as the Site Orchestrator. This boundary preserves manual GitHub Issue editing, keeps `escaping` independently reusable, and prevents authoring behavior or deployment credentials from leaking into the compiler.
