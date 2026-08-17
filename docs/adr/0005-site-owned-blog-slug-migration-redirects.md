---
status: accepted
---

# Keep Blog slug migration redirects in the site repository

When a published Blog entry changes its explicit front-matter slug, the site repository may
keep a temporary, explicit mapping and render static compatibility pages after the Site
Compiler has produced the new canonical page. This keeps migration history and retirement
under site ownership, while the compiler remains strict and does not infer redirects.

The mapping covers only non-.html slash-form Blog routes and must validate source/target state;
it does not generate title-derived slugs, revive historical .html aliases, or change the existing
decision in ADR-0003.
