# Finalize the reusable Config contract and safe links

Status: ready-for-human
Priority: P1 (execute before site Config cutover)
Blocked by: 02

## Outcome

Remove ignored Config fields, collapse duplicate link declarations, and reject unsafe rendered URLs before the first site-owned Config is adopted.

## Acceptance

- Ignored SEO/Branding/provider fields are rejected rather than silently accepted.
- Every Config value rendered into `href` or `src` follows an explicit safe URL policy.
- `javascript:`, `data:`, protocol-relative URLs, and control characters are rejected.
- Existing valid HTTPS and registered internal navigation continue to build.

## Comments

Introduced the discriminated Theme declaration and one safe `Link` model; validated avatar/branding/repository/comment values; removed ignored SEO toggles, Branding fields, and comments provider. Unsafe schemes, userinfo, protocol-relative destinations, whitespace/control data, and unsafe Theme manifest paths are rejected.
