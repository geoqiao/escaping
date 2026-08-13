---
status: accepted
---

# Use portable staged output publication instead of atomic directory exchange

The Site Compiler will continue to render and validate a complete candidate before replacing local output, but it will use portable directory renames with rollback rather than platform-specific `ctypes` bindings for atomic directory exchange. Failed production builds leave the deployed GitHub Pages artifact untouched because the Site Orchestrator does not run deployment after a failed build; the compiler's publication mechanism protects the local output tree and may permit a brief replacement window during a successful local rebuild.
