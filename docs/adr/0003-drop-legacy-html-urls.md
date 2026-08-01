---
status: accepted
---

# Drop legacy HTML URLs when adopting canonical routes

The site will replace historical `.html` Blog URLs with `/blog/{slug}/` and will not generate aliases or compatibility redirects. This deliberately accepts broken historical links and possible SEO loss in exchange for a single route model without migration machinery.
