# Theme authoring — API 4

A Theme turns your site's data into HTML pages. Three parts work together:

- **escaping** reads Issues, knows the kinds of pages a blog has (Home, the
  Blog, a post, …) and which template renders each kind, builds every address
  and checks the result.
- **The site's `config.yaml`** decides which of those pages exist and where:
  `pages.tags: false` removes the tag pages, `pages.blog: /posts/` moves the
  Blog, `pages.extra` adds pages such as `/now/`. See
  [Pages](../site-inputs.md#pages).
- **The Theme** supplies templates and static files. It needs only
  `blog.html` and `post.html`; the other page kinds fall back to them.

There are three ways to change the look. Start with the smallest one that does
what you need:

1. **Set Quiet's options** in `config.yaml`. No files to write.
2. **Extend Quiet**: a `theme/` directory with a two-line `theme.yaml` and only
   the files you want to replace.
3. **Write your own Theme** that does not depend on Quiet.

Coming from an older Theme? See [Migrating from API 3](#migrating-from-api-3).

## 1. Quiet's options

```yaml
theme:
  use: quiet # the default; this line can be left out
  options:
    tagline: Researcher / tool builder
    accent_color: "#2f6aa7"
    featured_posts: [41, 62]
```

[Quiet](quiet.md) lists every option. A misspelt option name or a wrong value
fails the build and names the option, for example
`theme.options.taglin: quiet has no such option; did you mean tagline?`.

## 2. Extend Quiet

```text
site/
├── config.yaml          # theme: {use: ./theme}
└── theme/
    ├── theme.yaml
    └── home-intro.html  # replaces Quiet's home-intro.html
```

`theme/theme.yaml`:

```yaml
api: 4
extends: quiet
```

`config.yaml`:

```yaml
theme:
  use: ./theme
```

A file in your Theme replaces Quiet's file with the same path. This works for
templates and for static files. Everything you do not provide comes from Quiet.
`use` must contain a `/` (`./theme`, `themes/mine`); a bare name such as
`quiet` means a built-in Theme. The path is relative to `config.yaml`, must stay
inside the site repository and must not overlap `paths.output`.

This replaces Quiet's Home introduction and adds a stylesheet to every page
(from `tests/fixtures/extends_theme`):

```jinja
{# theme/home-intro.html #}
<div class="home-intro">
  <p class="custom-intro">Custom introduction for {{ site.author }}. <a href="{{ site.routes.blog.canonical_path }}">{{ t.blog }}</a></p>
</div>
```

```jinja
{# theme/head-extra.html — Quiet includes it at the end of <head> #}
<meta name="x-now" content="{{ theme.now_text }}">
<link rel="stylesheet" href="{{ '/assets/css/extra.css'|url }}">
```

`theme/static/css/extra.css` is published at `/assets/css/extra.css`, next to
Quiet's files. Write it as `{{ '/assets/css/extra.css'|url }}` so it also
works for a site under a path (see [Addresses](#addresses)).
[Quiet](quiet.md#可以替换的文件) lists the partials that are meant to be
replaced.

### Reusing the file you replace

Inside a Theme that extends Quiet, `@quiet/` loads Quiet's own copy of a
template. Use it to add to a page instead of rewriting it:

```jinja
{# theme/home.html #}
{% extends "@quiet/home.html" %}
{% block content %}
{{ super() }}
<p>{{ t.hello }}</p>
{% endblock %}
```

Without the prefix, `home.html` would load your own file again. `@quiet/` is
only available when `theme.yaml` says `extends: quiet`.

Quiet's `base.html` reads three optional variables. Set them at the top of a
page template, outside any block:

| Variable | Used for | Default |
| --- | --- | --- |
| `page_title` | `<title>` (followed by ` · ` and the site title), Open Graph and Twitter titles | `site.title` |
| `page_description` | Meta, Open Graph and Twitter descriptions | `page.description` |
| `active_section` | The menu link whose `url` equals this path is marked current | `site.routes.home.canonical_path` |

A template for an extra page (`tests/fixtures/extends_theme/now.html`):

```jinja
{% extends "base.html" %}
{% set page_title = t.now_title %}
{% block content %}
<div class="page-heading"><h1>{{ t.now_title }}</h1><p class="now-text">{{ theme.now_text }}</p></div>
{% endblock %}
```

The site turns the page on in its `config.yaml`:

```yaml
pages:
  extra:
    - path: /now/
      template: now.html
```

Quiet's other templates also use `extends 'base.html'`, so a `base.html` in
your Theme changes every page.

## 3. Your own Theme

The smallest Theme has three files:

```text
site/theme/
├── theme.yaml       # api: 4
├── blog.html        # every list page
└── post.html        # every single page
```

`tests/fixtures/minimal_theme` is such a Theme. A site using it turns off the
two pages that have no fallback:

```yaml
pages:
  tags: false
  projects: false
```

### Which template renders a page

escaping looks for the first template in the chain that the Theme has
(with `extends`, the parent's files count too):

| Page kind (`page.kind`) | Templates, in order | Default address | Turned off by |
| --- | --- | --- | --- |
| `home` | `home.html`, `blog.html` | `/` | — |
| `blog` | `blog.html` | `/blog/`, `/blog/page/2/`, … | — (always on) |
| `post` | `post.html` | `/blog/<slug>/` | — |
| `ideas` | `ideas.html`, `blog.html` | `/ideas/` | `pages.ideas: false` |
| `idea` | `idea.html`, `post.html` | `/ideas/<Issue number>/` | `pages.ideas: false` |
| `about` | `about.html`, `post.html` | `/about/` | `pages.about: false` |
| `tags` | `tags.html` | `/tags/` | `pages.tags: false` |
| `tag` | `tag.html`, `blog.html` | `/tags/<tag key>/` | `pages.tags: false` |
| `projects` | `projects.html` | `/projects/` | `pages.projects: false` |
| `page` | the `template` named in `pages.extra` | the `path` named there | leaving it out |
| `404` | `404.html` (optional) | `/404.html`, served for any missing address | leaving out the file |

The addresses are the defaults; a site can move a section, for example
`pages.blog: /posts/`. Never write an address into a template; take it from a
[Route](#routes).

`blog.html` and `post.html` are required. When the tags or projects page is
on and the Theme has no `tags.html` or `projects.html`, the build stops before
reading any Issue and names both fixes:

```text
error: theme: has no tags.html for the tags page /tags/; add tags.html to the Theme, or set pages.tags: false in config.yaml
```

A page is never skipped silently. Extra templates (a `base.html`, includes,
macros) are yours to organise. `tests/fixtures/independent_theme` is a
complete Theme written only against this document.

## theme.yaml

```yaml
api: 4              # required
extends: quiet      # optional: a built-in Theme name
options: {}         # optional: settings a site can change
strings: {}         # optional: interface text per language
```

Unknown fields fail. `extends` can only name a built-in Theme; a local Theme
cannot extend another local Theme. When a Theme extends another, its `options`
and `strings` (by language and key) are merged over the parent's, and the
child wins.

A Theme does not declare pages. It ships the templates, and the site lists the
pages in `pages.extra` (see [Extra pages](#extra-pages)).

### options

```yaml
options:
  now_text:
    type: string
    default: Working on escaping.
    description: Shown on /now/ and in a head meta tag.
```

A site sets the value under `theme.options.now_text`; templates read
`{{ theme.now_text }}`. Every option needs a `type` and a `default`, and the
default must be a valid value. Option names start with a lowercase letter and
use lowercase letters, digits and `_`. A child Theme can redeclare a parent's
option to change its default.

| `type` | Accepted value | In templates |
| --- | --- | --- |
| `string` | text | text |
| `boolean` | `true` or `false` | bool |
| `integer` | a whole number | int |
| `color` | empty, or `#rgb` / `#rrggbb` | text |
| `url` | empty, or an HTTPS, `mailto:`, root-relative (`/…`) or `#fragment` link | text; pass a root-relative value through `url` |
| `choice` | one of `values` (required for this type) | text |
| `list` | a list of text | tuple of text |
| `posts` | a list of positive Blog Issue numbers, no repeats | tuple of [Blog posts](#content-models), in the listed order |

A `posts` number that is not a published Blog post is left out, and the build
reports the warning `THEME_OPTION_POST_MISSING`.

### strings

```yaml
strings:
  en:
    now_title: Now
  zh:
    now_title: 现在
```

Templates read `{{ t.now_title }}`. For `site.language: zh-CN`, `t` starts
with `en`, then applies `zh`, then `zh-cn` (language codes are not
case-sensitive). `t.language` is the most specific language that had strings
(`zh` here); use it for `lang` attributes on interface text. Keys follow the same
naming rule as options; `language` is reserved.

Define every key in `en`. A key that is missing for the site's language chain
fails rendering. A child Theme can override single keys of its parent, such as
Quiet's `footer_thanks`.

## Extra pages

A site adds pages that are not part of a blog, such as `/now/` or one page
per project, in its `config.yaml`:

```yaml
pages:
  extra:
    - path: /now/
      template: now.html
    - path: /projects/{slug}/
      template: project.html
      for_each: projects
```

- `path` is lowercase segments, each ending with `/`. It cannot be the address
  of another page, cannot be inside the Blog, Ideas or Tags section (they own
  every address below them) and cannot start with `/assets/`.
- `for_each: projects` renders the page once per project in the site's
  `projects` list. The path must contain `{slug}` exactly once, as a whole
  segment; other pages must not contain it. The template name may also contain
  `{slug}` (`projects/{slug}.html`) to give each project its own template.
- The Theme must have the named template, or the build stops before reading
  any Issue: `pages.extra: /now/ needs template now.html, which theme does not
  have`.
- On these pages `page.kind` is `page`; for `for_each` pages `page.project` is
  the project.
- The first `for_each` page of a project becomes `project.page`. Link to
  `project.page.canonical_path` when it is set; Quiet's project cards and the
  search index do this.
- A site can put the page in its menu: `site.navigation.items` accepts any
  root-relative URL that is a page of the site.

If your Theme offers templates for extra pages, list the `pages.extra` lines
in its README so a site can copy them.

## Template variables

Every template receives exactly four names:

| Name | What it is |
| --- | --- |
| `site` | Site-wide data, the same on every page |
| `page` | The page being rendered |
| `theme` | The Theme's options after defaults and the site's values |
| `t` | Interface text for the site's language |

Values are read-only. Missing fields fail loudly (Jinja `StrictUndefined`).
Optional values are `none`; test them with `{% if value %}` or
`is not none` (zero project stars is real data).

The template also has one filter of escaping's own, [`url`](#addresses).

### site

| Field | Meaning |
| --- | --- |
| `title`, `author`, `description`, `language` | From the site Config |
| `url` | Home URL, e.g. `https://example.com/` or `https://alice.github.io/notes/` |
| `repo` | Content repository, `owner/name` |
| `profile` | `avatar`, `bio` (text, may be empty) and `links` (each `name`, `url`) |
| `navigation` | The menu: each item has `name` and `url`. May be empty; render it as given |
| `comments` | `enabled` (bool) and `repo` (defaults to `site.repo`) |
| `seo` | `google_search_console`, `social_image` (absolute URL or empty), `social_image_alt` |
| `routes` | [Routes](#routes) for `home`, `blog`, `ideas`, `about`, `projects`, `tags`, `atom`, `search`. A page that is off is `none` |
| `posts` | Every Blog post, newest first |
| `ideas` | Every Idea, newest first (empty when Ideas are off) |
| `projects` | The site's projects, by `order`, then slug |
| `featured_projects` | Projects with `featured: true`, same order |
| `tags` | Every [Blog tag](#content-models), by tag key (empty when tags are off) |
| `about` | The About page, or `none` when it is off |

Link to a section only when it is on:

```jinja
{% if site.routes.tags %}<a href="{{ site.routes.tags.canonical_path }}">{{ t.tags }}</a>{% endif %}
```

### page

Every page has all of these fields; the ones a page does not use are `none`.
This is why one `blog.html` can render every list and one `post.html` every
single item.

| Field | Meaning |
| --- | --- |
| `kind` | See [the table above](#which-template-renders-a-page) |
| `route` | The page's [Route](#routes); `none` on `404` |
| `description` | Summary for the meta description: the item's own on a post, Idea or About, the project's summary on a `for_each` page, otherwise `site.description` |
| `json_ld` | Structured data for Home, posts, Ideas and About; otherwise `none`. Output it with `{{ page.json_ld\|tojson }}` inside `<script type="application/ld+json">` |
| `item` | The one thing a single page shows: the post, the Idea or the About page |
| `items` | What a list page shows: posts on `home`, `blog` and `tag`; Ideas on `ideas`; Tags on `tags`; projects on `projects` |
| `pagination` | On list pages: `number`, `total`, `prev` (the Route of the newer page or `none`), `next` (the older page or `none`). Only the Blog has more than one page; Home shows the Blog's first page |
| `newer`, `older` | On `post` and `idea`: the neighbouring item (`none` at either end) |
| `tag` | On `tag`: the tag |
| `project` | On a `for_each` page: the project |

A tag page in `blog.html`:

```jinja
<h1>{{ page.tag.name if page.tag else t.blog }}</h1>
{% for post in page.items %}
<a href="{{ post.canonical_path }}">{{ post.title }}</a>
{% endfor %}
{% if page.pagination.next %}<a rel="next" href="{{ page.pagination.next.canonical_path }}">{{ t.older }}</a>{% endif %}
```

On `ideas`, `tags` and `projects`, `page.items` holds Ideas, Tags or projects.
A `blog.html` that also renders `ideas` reads fields every item has (`title`,
`canonical_path`, `created_date`); give the Theme its own `tags.html` and
`projects.html`, because those items differ.

### Routes

| Field | Example |
| --- | --- |
| `canonical_path` | `/blog/notes/` — use this for links |
| `canonical_url` | `https://example.com/blog/notes/` — use this for canonical and `og:url` |
| `output_path` | `blog/notes/index.html` |
| `name` | `blog-detail-notes` |

Paths are percent-encoded, so a Chinese tag links correctly. Never build an
address from a title, slug, number or tag name; take it from a Route.

### Content models

Posts, Ideas and About pages share the fields a single page needs, so one
`post.html` can show all three:

| Field | Post | Idea | About from an Issue | About from the profile |
| --- | --- | --- | --- | --- |
| `title`, `description`, `body_html`, `route`, `canonical_path`, `canonical_url` | ✓ | ✓ | ✓ | ✓ (`body_html` is the bio, may be empty) |
| `issue_number` | ✓ | ✓ | ✓ | `none` |
| `created_date` | ✓ | ✓ | ✓ | empty |
| `tags` (each `name`, `path`) | Blog tags | Idea tags | empty | empty |
| `is_profile` | — | — | false | true |

- A Blog tag also has `key` and `route`; its `path` is `none` when the tags
  pages are off. An Idea tag has only `name` and `path` (always `none`). Link a
  tag when `tag.path` is set, otherwise show the name as text.
- Blog posts also have `slug`, `published_at` and `updated_at`; Ideas have
  `published_at` and `updated_at`.
- `created_date` is a `YYYY-MM-DD` string, fine for display and
  `<time datetime>`. `published_at` and `updated_at` are timezone-aware
  datetimes.

| Model | Fields |
| --- | --- |
| Tag (`site.tags`, `page.tag`) | `name`, `key`, `count`, `posts` (newest first), `route`, `canonical_path`, `canonical_url` |
| Project | `slug`, `title`, `summary`, `url` (website, else repository), `repository`, `repository_url`, `website`, `featured`, `order`, `stars`, `forks`, `language`, `topics`, `image`, `links` (each `name`, `url`), `page` |

Show comments only for an item with an `issue_number`:

```jinja
{% if page.item.issue_number and site.comments.enabled %}
{% set comments_issue_number = page.item.issue_number %}
{% include "_comments.html" %}
{% endif %}
```

A profile About never shows comments.

### HTML and escaping

Autoescape is on. `body_html` is sanitised by escaping and is the only content
to mark `|safe`. Titles, descriptions, tags, profile text, options and strings
are plain text; let autoescape handle them. Output `page.json_ld` with
`|tojson`, never as a string with `|safe`.

Jinja does not pass the page context into imported macros by default. Import
with `with context` when a macro reads `site`, `page`, `theme` or `t`, as Quiet
does: `{% from 'components.html' import tags with context %}`.

## Addresses

A site may live at the root of a host (`https://example.com/`) or under a
path (`https://alice.github.io/notes/`, a GitHub project site). escaping
handles the difference for everything it builds:

- Route paths already include the site's path: under `/notes/`, the Blog's
  `canonical_path` is `/notes/blog/`.
- Links in Issues, `site.navigation`, `site.profile`, `site.seo.social_image`
  and project images and links are already adjusted.

The Theme adjusts its own addresses with the `url` filter:

```jinja
<link rel="stylesheet" href="{{ '/assets/css/style.css'|url }}">
<script src="{{ '/assets/escaping/comments.js'|url }}" defer></script>
<a href="{{ theme.cta_link|url }}">…</a>   {# a `url` option may be root-relative #}
```

`url` puts a root-relative address under the site's path. Full URLs,
`#fragments` and addresses that already start with the site's path stay as
they are, so it is safe on a value that may already be adjusted. At the root
of a host it changes nothing, which is why a missing `url` goes unnoticed
until a site under a path uses the Theme. The build then fails with
`LINK_OUTSIDE_SITE` and names the fix. Test your Theme with a site under a
path before sharing it (see [Checks](#checks)).

## Static and shared assets

Everything under your Theme's `static/` is published under `/assets/`:
`static/css/style.css` becomes `/assets/css/style.css`. With `extends`, your
files and the parent's are combined and yours win on the same path. Files and
folders starting with `.` are skipped. Reference assets as
`{{ '/assets/…'|url }}`, not with relative paths, so they also work from
`404.html`, which is served at any depth. Inside a stylesheet, refer to other
static files relatively (`url("../fonts/x.woff2")`).

- Symbolic links anywhere in a Theme are rejected; copy the file instead.
- `static/escaping/` is reserved and fails the build.
- Do not put `.html` files in `static/`; an HTML file that is not a page of the
  site fails the build.

escaping publishes shared scripts under `/assets/escaping/` for every Theme.
Use them instead of copying their code.

| File | Purpose |
| --- | --- |
| `/assets/escaping/comments.js` | Utterances comments |
| `/assets/escaping/mermaid.js` | Loads the Mermaid runtime on pages with diagrams |
| `/assets/escaping/mermaid/mermaid.min.js` | The bundled Mermaid runtime (with its `LICENSE` and `README.md`) |

### Comments

Comments are off unless the site sets `comments.enabled: true` and installs the
[Utterances GitHub App](https://github.com/apps/utterances) on the repository.
Show them only on pages backed by an Issue (posts, Ideas, an Issue About) and
only when `site.comments.enabled` is true. The markup, from Quiet's
`components.html`:

```jinja
<div id="comments-container"
     data-issue-number="{{ number }}"
     data-comments-repo="{{ site.comments.repo }}"
     data-source-repo="{{ site.repo }}"
     data-comments-theme="github-light"
     data-comments-theme-mode="auto"
     data-blog-theme-default="light">
  <p class="comments-loading" role="status">Loading comments…</p>
</div>
<script src="{{ '/assets/escaping/comments.js'|url }}" defer></script>
```

| Attribute | Meaning |
| --- | --- |
| `data-issue-number` | The Issue the thread belongs to |
| `data-comments-repo` | Repository holding the thread |
| `data-source-repo` | Content repository, for the fallback link to the Issue |
| `data-comments-theme-mode` | `auto`: follow `<html data-theme="light\|dark">` (github-light / photon-dark). `fixed`: always use `data-comments-theme` |
| `data-comments-theme` | An Utterances theme name, used when the mode is `fixed` |
| `data-blog-theme-default` | `light` or `dark`, used while `<html>` has no `data-theme` |
| `data-unavailable-text` | Optional. Message shown if comments cannot load; English by default |
| `data-issue-link-text` | Optional. Text of the fallback link to the Issue; English by default |

Use one container per page. The optional `.comments-loading` element is
replaced by a link to the Issue if comments cannot load. Quiet exposes the
colour settings as its `comments_theme` and `comments_theme_mode` options; your
Theme can do the same or hard-code them.

### Diagrams

A ```` ```mermaid ```` block in an Issue becomes `<pre><code
class="language-mermaid">`. To draw it, add the loader on pages whose body can
contain diagrams:

```jinja
<script src="{{ '/assets/escaping/mermaid.js'|url }}"
        data-runtime-src="{{ '/assets/escaping/mermaid/mermaid.min.js'|url }}"
        data-mermaid-theme="neutral" defer></script>
```

`data-mermaid-theme` is a Mermaid theme name, or `auto` to pick dark or default
from `<html data-theme>`. The loader does nothing on pages without diagrams, and
the source stays readable if it fails.

### Files escaping writes

`/atom.xml`, `/sitemap.xml`, `/search.json` and, at the root of a host,
`/robots.txt` are not templates. The sitemap lists every page, including
extra pages. Old addresses listed under `redirects` in `config.yaml` become
small pages that send visitors on; they do not use the Theme.
`site.routes.search.canonical_path` points to the search index:

```json
{"version": 1, "items": [{"title": "…", "description": "…", "tags": ["…"], "type": "Blog", "url": "/blog/notes/"}]}
```

`type` is `Blog`, `Idea` or `Project`. Items are Blog posts (newest first),
then Ideas, then projects; a project's `url` is its `project.page` when it has
one. Every `url` already includes the site's path. Search covers titles,
summaries and tags, not full text. If you put the address in a
`data-search-index` attribute on a `<script>`, the build checks that it
exists. Insert results with `textContent`, never as HTML.

## Checks

### Every build

Before reading any Issue, the build checks the Config, loads the Theme, checks
the site's `theme.options`, and compiles every template. It stops if a
template a page needs is missing, or if a template has a syntax error
(reported with file and line).

After rendering, and before replacing the published output, it checks
integrity:

| Code | Meaning |
| --- | --- |
| `MISSING_ROUTE` | A page has no file |
| `UNREGISTERED_HTML` | An `.html` file that is not a page of the site (`404.html` is allowed) |
| `BROKEN_INTERNAL_LINK` | A link or resource on this site that is neither a page nor a file |
| `LINK_OUTSIDE_SITE` | For a site under a path: a root-relative address outside it, usually a missing `url` filter |
| `INVALID_INTERNAL_PATH` | An unsafe internal URL, such as `..` or control characters |

Checked references are `href` on `<a>` and `<link>`; `src` on `<script>`,
`<img>` and `<source>`; `srcset`; `data-runtime-src` and `data-search-index`
on `<script>`; and `og:image` / `twitter:image`. Relative links are resolved
against the page URL. Links to other sites are not checked. A template error
while rendering (such as an undefined variable) also fails the build. A failed
build leaves the previously published output unchanged.

The build does not check titles, descriptions, canonical links or structured
data. How a Theme writes its `<head>` is up to the Theme.

### escpe theme check

```bash
escpe theme check --config config.yaml
```

This renders the site offline with a few sample Issues (two Blog posts with
tags, code, a table and a diagram, an Idea and an About Issue, for the pages
that are on) and the site's own pages, options and projects. It needs no
token. It reports everything a build would, plus these warnings for each page
in the sitemap:

| Code | Meaning |
| --- | --- |
| `SEO_TITLE` | No `<title>` |
| `SEO_DESCRIPTION` | No meta description |
| `SEO_CANONICAL` | Not exactly one `<link rel="canonical">` equal to `page.route.canonical_url` |
| `SEO_URL` | `og:url` or `twitter:url` differs from the canonical URL |

To try real content, save your Issues with
`gh api --paginate --slurp 'repos/OWNER/REPO/issues?state=all&per_page=100' > issues.json`
and add `--issues-json issues.json`. From a checkout of escaping, prefix the
command with `uv run` (see [Local build](../site-inputs.md#local-build)).

A passing check is not a full review. Also look at the pages in a browser:
narrow screens, keyboard navigation, light and dark, empty collections, both
About variants, and comments on and off.

## Sharing a Theme

A Theme is a folder. To let other people use yours, publish that folder, for
example as its own Git repository, with:

- `theme.yaml` (`api: 4`) and the templates and `static/` files;
- a README that says which escaping version it was made for, which pages it
  has templates for (and which `pages.*: false` a site needs otherwise), its
  options, and the `pages.extra` lines for any extra-page templates it ships;
- a license.

Before you publish, run `escpe theme check` with at least two configs: one at
the root of a host with every page on, and one under a path
(`site.url: https://example.github.io/demo/`) with the pages you do not
support turned off.

Someone who wants the Theme copies the folder into their site repository and
selects it:

```yaml
theme:
  use: ./themes/paper
```

escaping never downloads a Theme, so updating is copying the new version over
the folder. A Git submodule also works; then the site's workflow must check it
out (`actions/checkout` with `submodules: true`). Only Quiet ships with
escaping; there is no Theme registry.

## Security

A Theme is trusted code: its templates and JavaScript run on your site. Review a
Theme before using it. escaping never runs Python from a Theme and never
downloads one; it reads only the built-in Themes and the local directory named
by `theme.use`. Autoescape is not a sandbox for untrusted templates.

## Migrating from API 3

API 3 Themes stop the build with
`theme.yaml must declare api: 4 (see docs/themes/authoring.md#migrating-from-api-3)`.
Change `api: 3` to `api: 4`, then:

| API 3 | API 4 |
| --- | --- |
| `pages:` in `theme.yaml` | Stops the build: `theme.yaml pages: moved to pages.extra in the site's config.yaml`. Move each entry, unchanged, under `pages.extra` in the site's `config.yaml`, and list them in the Theme's README |
| All nine page templates required | Only `blog.html` and `post.html`; see [the table](#which-template-renders-a-page) |
| `page.post`, `page.idea`, `page.about` | `page.item` |
| `page.archive.posts` | `page.items` |
| `page.archive.page_number`, `total_pages`, `prev_route`, `next_route` | `page.pagination.number`, `total`, `prev`, `next` |
| `page.tag.posts` on a tag page | `page.items` (`page.tag` is still the tag) |
| `site.ideas`, `site.tags`, `site.projects` on their list pages | `page.items` (the `site` fields still exist) |
| `site.routes.<name>` always set | `none` when the site turns that page off; guard links with `{% if site.routes.tags %}` |
| `site.about` always set | `none` when `pages.about: false` |
| Profile About had no `body_html` | It has `body_html` (the bio), `issue_number: none`, empty `created_date` and `tags` |
| Blog tags always had a page | `tag.path` is `none` when `pages.tags: false`; Idea tags have `path: none` too |
| `href="/assets/…"` | `href="{{ '/assets/…'|url }}"`, needed for sites under a path |
| `/robots.txt` always written | Only at the root of a host |

## Migrating from API 2

API 2 Themes stop the build with
`theme.yaml must declare api: 4 (see docs/themes/authoring.md#migrating-from-api-2)`.
There is no compatibility layer. For a Theme that only changed parts of Quiet,
it is usually easier to start again with `extends: quiet` and copy over just
the changed files. Otherwise, apply these tables, then
[Migrating from API 3](#migrating-from-api-3).

| API 2 | API 3 |
| --- | --- |
| `api_version: "2"`, `capabilities`, `required_templates`, `required_assets` | `api: 3`. The other fields are gone |
| `index.html` (Blog archive) | `blog.html` |
| `{{ theme_path }}/static/…` (`/templates/<name>/static/…`) | `/assets/…` |
| Shared `…/static/js/comments.js`, `…/static/js/mermaid.js`, `…/static/vendor/mermaid-11.16.1/mermaid.min.js` | `/assets/escaping/comments.js`, `/assets/escaping/mermaid.js`, `/assets/escaping/mermaid/mermaid.min.js` |
| Page variables defined only on some templates | Every page gets the same `page` object; unused fields are `none` |
| Build failed on canonical, social URL and JSON-LD problems | `escpe theme check` warns; the build checks integrity only |
| Quiet's interface was English for every language | `site.language: zh` or `zh-CN` switches Quiet to Chinese |

Template variables:

| API 2 | API 3 |
| --- | --- |
| `blog_title`, `author_name`, `language` | `site.title`, `site.author`, `site.language` |
| `meta_description` | `page.description` (the site's is `site.description`) |
| `github_repo` | `site.repo` |
| `page_canonical_url` | `page.route.canonical_url` |
| `site_routes.<name>`, `home_path`, `atom_url` | `site.routes.<name>`, `site.routes.home.canonical_path`, `site.routes.atom.canonical_url` |
| `navigation_items` | `site.navigation` |
| `metadata.profile` | `site.profile` (`tagline` is now a Quiet option) |
| `comments` | `site.comments` (`theme` / `theme_mode` are now Theme options) |
| `metadata.social_image`, `metadata.social_image_alt`, `google_search_verification` | `site.seo.social_image`, `site.seo.social_image_alt`, `site.seo.google_search_console` |
| `structured_data` | `page.json_ld` |
| `home_page.recent_posts` | `site.posts[:5]` |
| `home_page.featured_posts` | A `posts` option, such as Quiet's `featured_posts` |
| `archive_page` (`entries`) | `page.archive` (`posts`) |
| `post`, `prev_post`, `next_post` | `page.post`, `page.newer`, `page.older` |
| `ideas`, `idea` | `site.ideas`, `page.idea` |
| `about_page`, `about_is_profile` | `page.about`, `page.about.is_profile` |
| `projects.projects`, `featured_projects` | `site.projects`, `site.featured_projects` |
| `tags_index.tags` | `site.tags` |
| `tag_archive` (`tag_name`, `entries`) | `page.tag` (`name`, `posts`) |
| `detail_path` | `canonical_path` |
| `skip_link_text` and other fixed text | Your own `strings` |
| `theme_path`, `theme_favicon_url`, `author_initials`, `branding`, `metadata.thesis`, `top_projects` | Removed. Use `/assets/…`, compute in the template, or declare an option |

Site Config:

| Old field | New place |
| --- | --- |
| `theme: {source: builtin, name: Quiet}` | `theme: {use: quiet}` (or leave it out) |
| `theme: {source: local, name: x, path: theme}` | `theme: {use: ./theme}` |
| `site.featured_posts` | `theme.options.featured_posts` |
| `profile.tagline` | `theme.options.tagline` |
| `branding` | `theme.options.show_powered_by` |
| `comments.theme`, `comments.theme_mode` | `theme.options.comments_theme`, `theme.options.comments_theme_mode` |
| `site.thesis` | Removed; declare it as an option of your own Theme |

The build names each old field and where it went.

## Migrating from API 1

API 1 Themes are rejected the same way. Follow
[Migrating from API 2](#migrating-from-api-2); no API 1 name carries over on
its own.

## Migrating removed built-in Themes

`geoqiao.me`, `Escape1` and `Escape2` are no longer shipped, and Quiet is now
spelled `quiet`. Selecting another name fails and leaves the published site
unchanged; it never falls back to Quiet silently.

| You want | Do this |
| --- | --- |
| Quiet | `theme: {use: quiet}`, or remove `theme` |
| To keep an old design | Copy its directory from the escaping version you used into the site repository, port it with [Migrating from API 2](#migrating-from-api-2), and select it with `theme: {use: ./that-directory}` |

Assets of the copied Theme move from `/templates/<name>/static/` to
`/assets/`. Upgrade escaping, the Config and the local Theme together, check
them with `escpe theme check` and a local build, and deploy separately; see
[deployment](../deployment.md).
