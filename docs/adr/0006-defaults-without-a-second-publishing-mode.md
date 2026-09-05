---
status: accepted
---

# Provide defaults without a second publishing mode

Requiring front matter and a complete site configuration makes ordinary Issue
writing depend on generator knowledge. The compiler therefore derives missing
content metadata from Issue identity, native timestamps, and sanitized visible
body text; missing site values use trusted repository, Pages, and public profile
inputs. Explicit values override fields independently and remain strictly
validated: invalid input is not a request for fallback.

Basic and advanced authoring use one current contract and one compiler, not
parallel modes or a compatibility parser. Missing About content can produce a
Profile About page without inventing an Issue or discussion thread. Author and
publication gates, explicit Settings injection, Config-relative paths, and
staged validation remain unchanged; defaults confer no remote write authority.

This trades fully authored metadata for a simpler first publication while
preserving deliberate overrides. A stateless compiler cannot infer historical
slug changes, and default profile data is not a substitute for a failed content
fetch. The one-way authoring and site-orchestration boundaries in ADR-0001 and
ADR-0002 continue to apply.
