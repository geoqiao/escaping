# Minimal Theme fixture

Only `blog.html` and `post.html`, used by the template fallback tests.

- Home, Ideas and tag pages render with `blog.html` (`page.items`,
  `page.pagination`, and `page.tag` on a tag page).
- Blog posts, Ideas and About render with `post.html` (`page.item`, plus
  `page.newer` and `page.older`).
- It has no `tags.html` or `projects.html`, so a site using it must set
  `pages.tags: false` and `pages.projects: false`.
