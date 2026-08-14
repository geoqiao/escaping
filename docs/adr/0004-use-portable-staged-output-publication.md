---
status: accepted
---

# Use portable staged output publication instead of atomic directory exchange

The Site Compiler will continue to render and validate a complete candidate before replacing local output, but it will use portable directory renames with rollback rather than platform-specific `ctypes` bindings for atomic directory exchange. Failed production builds leave the deployed GitHub Pages artifact untouched because the Site Orchestrator does not run deployment after a failed build; the compiler's publication mechanism protects the local output tree and may permit a brief replacement window during a successful local rebuild.

## Accepted limits

Staging ownership checks run before each mutation, but the interval between a check and its
mutation remains a known local TOCTOU window; closing it would require fd-based operations outside
this decision's scope. Concurrent local builds targeting the same output directory are unsupported,
because this design provides no build lock.
