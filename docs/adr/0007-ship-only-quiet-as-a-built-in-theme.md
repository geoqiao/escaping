---
status: accepted
---

# Ship only Quiet as a built-in Theme

The product is a low-friction, content-first personal site, not a collection of
built-in designs. Keep Quiet and remove geoqiao.me, Escape1 and Escape2 rather
than maintaining parallel templates, assets and theme-specific regressions.
Independently maintained local Themes remain supported through Theme API 2;
this does not remove its public fields or weaken compilation/publication safety.

An explicit removed built-in selection must fail without replacing old output,
never silently change the site's design. Site owners can select Quiet or retain
a reviewed copy of their previous design as a local Theme before upgrading;
see the [migration contract](../themes/authoring.md#migrating-removed-built-in-themes).
This trades built-in choice for a smaller maintenance surface, not for automatic
site migration or deployment authority.
