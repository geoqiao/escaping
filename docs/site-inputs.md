# Site inputs: the Config and where missing values come from

A site is built from its Issues and one `config.yaml`. Almost every field is
optional: the command line fills missing values once, before compiling, from
the repository, its Pages settings and the owner's public GitHub profile.
Rendering never reads the Config or calls GitHub.

For the normal hosted setup, follow the [starter instructions](../starter/README.md).
[config.example.yaml](../config.example.yaml) lists every field; it is a
reference, not a list of required fields.

## Two layers

The Config has two layers. To decide where a value belongs, ask: does it still
mean something after switching to another Theme?

- **Site fields** keep their meaning with any Theme:

  | Section | Holds |
  | --- | --- |
  | `github` | `repo` (owner/name) and `allowed_authors` |
  | `site` | `title`, `url`, `author`, `description`, `language`, `navigation` |
  | `profile` | `avatar`, `bio`, `links` |
  | `about` | `issue_number` |
  | `paths` | `output`, `page_size` |
  | `pages` | which pages exist and where; see [Pages](#pages) |
  | `redirects` | old addresses and where they went; see [Redirects](#redirects) |
  | `projects` | the curated project list |
  | `comments` | `enabled`, `repo` (Utterances) |
  | `seo` | `google_search_console`, `social_image`, `social_image_alt` |
  | `security` | `token_env`: the NAME of the token variable, never the token |

- **Theme options** belong to the selected Theme. The Theme's `theme.yaml`
  declares each option with a type and a default; the site sets values under
  `theme.options`:

  ```yaml
  theme:
    use: quiet          # a built-in Theme, or a directory next to the Config: ./theme
    options:
      tagline: Researcher / tool builder
      featured_posts: [41, 62, 49]
  ```

  An unknown option name or a wrong type fails with the option's name and, for
  a typo, the closest correct name. Quiet's options are listed in
  [Quiet](themes/quiet.md); writing a Theme is covered in the
  [Theme guide](themes/authoring.md).

`site.language` is a site field, but a Theme also uses it to pick its interface
text: Quiet shows Chinese for `zh` or `zh-CN`, English otherwise.

Every section rejects unknown fields. Fields that moved in 0.2 are named with
their new place, for example `site.featured_posts: moved to
theme.options.featured_posts`. Errors name the field and the reason; they never
repeat the value you wrote.

## CLI inputs

```text
escpe build        [--config FILE] [--issues-json FILE] [--context FILE] [--repo OWNER/NAME] [--token-env NAME]
escpe theme check  [--config FILE] [--issues-json FILE]
```

`build` is the default, so `escpe --config config.yaml` also builds.
`--config` defaults to `config.yaml` in the current directory.

| Exit status | Meaning |
| --- | --- |
| 0 | The site was published. |
| 1 | Nothing was published; the previous output is unchanged. |
| 2 | The site was published, but some Issues were skipped because of their own errors. |

Problems are printed as `error: …` or `warning: …` lines. On GitHub Actions
the command also writes error annotations, a job summary that links each
problem to its Issue, and the step outputs `output` (the output directory) and
`skipped-issues` (comma-separated numbers).

Without platform context, the Config needs at least the real content
repository and the real HTTPS site URL (not a guessed Pages URL):

```yaml
github:
  repo: alice/site
site:
  url: https://notes.example/
```

With a token, the owner and the missing profile fields are read from GitHub.
An Organization must list `github.allowed_authors`.

In GitHub Actions the [Action](deployment.md#the-reusable-action) writes a
small platform snapshot and passes it with `--context`, so `config.yaml` can
be `{}`:

```json
{
  "repository": "alice/site",
  "owner_login": "alice",
  "owner_type": "User",
  "pages_base_url": "https://notes.example/"
}
```

The file has exactly these four fields. Only GitHub.com User or Organization
owners and HTTPS Pages URLs are supported. A project site such as
`https://alice.github.io/site/` works: its path becomes the site's path (see
[Sites under a path](#sites-under-a-path)). The context never holds a token,
an actor or Config overrides.

`--repo owner/name` overrides `github.repo`. It, or a Config repository that
differs from the context, makes the CLI verify that repository through GitHub
again. A renamed or redirected repository never silently becomes the content
source; change the Config on purpose.

`--token-env NAME` picks the token variable for one run and overrides
`security.token_env`. The default variable is `GITHUB_TOKEN`.

## Local build

You need Python 3.14.x and [uv](https://docs.astral.sh/uv/). Clone the
generator and keep your site in its own directory:

```bash
git clone https://github.com/geoqiao/escaping.git
cd escaping
uv sync --locked
mkdir -p ../my-site
```

Save the minimal YAML from [CLI inputs](#cli-inputs) as
`../my-site/config.yaml`, with your real repository and site URL.

**With a token.** A token that can read the repository's Issues lets the CLI
fill the title, author, avatar and bio from your public profile:

```bash
export GITHUB_TOKEN=...   # or the variable named in security.token_env
uv run escpe build --config ../my-site/config.yaml
```

**Offline.** Save the Issues once with the [GitHub CLI](https://cli.github.com/)
and build from the file. Without a token, the Config must also set everything
that would otherwise come from GitHub: `github.allowed_authors`, `site.title`,
`site.author`, `site.description`, `profile.avatar` and `profile.bio` (empty
strings are fine). The error message lists what is missing.

```bash
gh api --paginate --slurp 'repos/OWNER/REPO/issues?state=all&per_page=100' > ../my-site/issues.json
uv run escpe build --config ../my-site/config.yaml --issues-json ../my-site/issues.json
```

Projects are not enriched from GitHub in an offline build; they use the
values in the Config and their `fallback_metadata`.

**Preview.** Serve the output directory as the web root, never under an
`/output/` URL prefix:

```bash
uv run python -m http.server 8000 --directory ../my-site/output
```

Open <http://localhost:8000>. For a site under a path such as
`https://alice.github.io/notes/`, the pages link to `/notes/…`; serve a
directory that holds the output as `notes`:

```bash
mkdir -p ../preview && ln -sfn "$PWD/../my-site/output" ../preview/notes
uv run python -m http.server 8000 --directory ../preview
```

and open <http://localhost:8000/notes/>.

**Check a Theme.** `escpe theme check` renders a few sample Issues (a post
with a table, code and a Mermaid diagram, an Idea and an About) with your
Theme and options. It needs no token or network, and also reports SEO
warnings that a normal build does not check:

```bash
uv run escpe theme check --config ../my-site/config.yaml
```

Add `--issues-json` to check with your real Issues instead.

**The output directory is replaced on every build.** It must be `output`,
`_site`, `public`, `dist` or `build` (or a directory inside one of them),
relative to the Config file. escaping writes a `.escaping-output` file into
it. A build refuses to replace a non-empty directory without that file, so it
never deletes files it did not write. An output directory from escaping 0.1
has no marker: move out anything you want to keep and delete it once.

## Missing-field sources

| Config field | Value when absent |
| --- | --- |
| `github.repo` | The context repository; otherwise required |
| `github.allowed_authors` | The verified owner login of a User account (never the workflow actor); an Organization must list authors |
| `site.url` | The Pages URL from the context (with its path for a project site); otherwise required |
| `site.title`, `site.author` | The owner's public name, otherwise the owner login |
| `site.description` | The owner's public bio, otherwise empty |
| `site.language` | `en` |
| `site.navigation.items` | Home, Blog, then Projects, Tags and About when they are on, then RSS |
| `pages` | Every page on at its usual address; no extra pages |
| `redirects` | None |
| `profile.avatar`, `profile.bio` | The owner's public avatar and bio, otherwise empty |
| `about.issue_number` | The oldest published About Issue; without one, a Profile About page |
| `paths.output`, `paths.page_size` | `output`, `10` |
| `projects` | None; the owner's repositories are never listed automatically |
| `theme.use` | `quiet` |
| `theme.options` | Each option's default from the Theme's `theme.yaml` |
| `comments.enabled` | `false`; only a real YAML boolean is accepted |
| `comments.repo` | `github.repo` |
| `seo.social_image`, `seo.social_image_alt` | Empty: no preview image |
| `security.token_env` | `GITHUB_TOKEN` |

The default menu follows `pages`: a moved Blog is linked at its new address and
a page that is off is left out. It leaves out Ideas; add `/ideas/` to an
explicit `site.navigation.items` list to show it. An explicit list replaces the
whole menu, and `items: []` means no menu. A root-relative menu link must point
at a page of the site, or the build fails; for a page that is off it says so,
for example `navigation item Tags points to /tags/, which is not a page of this
site (pages.tags is false)`.

Only absent fields get defaults. Explicit empty strings, `false` and empty
lists are kept. Nested sections resolve field by field; lists replace as a
whole. Null values, unknown fields, unsafe URLs, duplicate YAML keys and other
invalid values fail instead of falling back.

For profile defaults only the public `login`, `name`, `avatar_url` and `bio`
are read. If that request fails, the build warns with
`PROFILE_ENRICHMENT_FAILED` and uses the owner login with an empty avatar and
bio. If the repository or its Issues cannot be read, the build fails and the
previous output stays. Error text from GitHub is never shown.

### Shared social preview image

`seo.social_image` is an optional HTTPS or root-relative image URL;
`seo.social_image_alt` is its optional alternative text. A root-relative value
is turned into an absolute URL on `site.url`. It must be a file the Theme
publishes, such as `/assets/images/og.png` from the Theme's
`static/images/og.png`; otherwise the build fails with a broken-link error.
An external image is not downloaded or checked.

Quiet puts the image in `og:image` and `twitter:image` and switches the
Twitter card to `summary_large_image`. The alt tags appear only when the alt
text is not empty. Without an image, Quiet keeps a `summary` card. Other
Themes decide for themselves whether to show the image.

## Pages

escaping knows the kinds of pages a blog has. `pages` decides which of them
the site has and at which address. Each section takes `true` (on, at its usual
address), `false` (off) or a path:

```yaml
pages:
  blog: /posts/        # the Blog cannot be turned off; move it with a path
  ideas: false
  tags: true
  projects: true
  about: /me/
  extra:
    - path: /now/
      template: now.html
    - path: /projects/{slug}/
      template: project.html
      for_each: projects
```

| Key | Usual address | When it is off |
| --- | --- | --- |
| `blog` | `/blog/` (posts at `/blog/<slug>/`, older pages at `/blog/page/2/`) | cannot be off |
| `ideas` | `/ideas/` (each at `/ideas/<Issue number>/`) | `type:idea` Issues are not published; each gets the warning `PAGE_OFF` |
| `tags` | `/tags/` (each at `/tags/<tag key>/`) | tags still show on posts, without links |
| `projects` | `/projects/` | the `projects` list can still feed Home or extra pages |
| `about` | `/about/` | an About Issue is not published and gets `PAGE_OFF`; `about.issue_number` must not be set |

Home is always `/`. A path is lowercase segments ending with `/`. Two pages
cannot share an address, one section cannot sit inside another, and nothing can
start with `/assets/`, where static files live. The Blog, Ideas and Tags own
every address below them, so an extra page cannot be at `/blog/now/`.

`extra` adds pages that are not part of a blog. Each names a `path` and the
Theme `template` that renders it; the Theme must have that template, or the
build stops before reading any Issue. `for_each: projects` renders one page per
project; its path contains `{slug}` once, and the template name may too
(`projects/{slug}.html`). A Theme's README lists the extra pages it has
templates for. See the [Theme guide](themes/authoring.md#extra-pages).

The Theme must have a template for every page that is on. Quiet has all of
them. A small Theme may have only `blog.html` and `post.html`; then the build
names what to add, or which page to turn off:

```text
error: theme: has no tags.html for the tags page /tags/; add tags.html to the Theme, or set pages.tags: false in config.yaml
```

## Redirects

When an address changes, keep the old one working:

```yaml
redirects:
  /blog/old-slug/: /blog/new-slug/
  /old-about.html: /about/
```

Each old address becomes a small page that sends visitors and search engines
to the new one at once (`<meta http-equiv="refresh">` plus a canonical link;
GitHub Pages cannot send real HTTP redirects). It is not in the sitemap.

- The old address is a path of this site ending with `/` (it then answers
  `/old` and `/old/`) or `.html`. `/`, `/index.html`, `/404.html` and
  `/assets/…` cannot redirect. Non-ASCII paths may be written plainly or
  %-encoded.
- The new address is a path of this site. It may be another old address;
  the chain is followed to the page. A circle fails the build.
- The same old address twice (ignoring case) fails the build.
- A page always wins: if the old address is a page again, or the new address
  is no page (for example its Issue was unpublished), that redirect is left
  out with the warning `REDIRECT_LEFT_OUT` and the rest of the site still
  publishes.

## Sites under a path

A site can live at the root of a host (`https://notes.example/`) or under a
path (`https://alice.github.io/notes/`, a GitHub project site). On GitHub
Actions the path comes from the Pages settings; without context, write it in
`site.url`. Nothing else changes in the Config: addresses in `pages`,
`redirects`, `site.navigation`, `profile`, `seo.social_image` and `projects`
are written from the site's own root (`/about/`), and escaping puts them under
the path. Links in Issues work the same way, so `[About](/about/)` in an Issue
links to `/notes/about/`.

`robots.txt` is not written for a site under a path, because crawlers read it
only at the root of a host. The sitemap is still at `/notes/sitemap.xml`.

A Theme must write its own static files as `{{ '/assets/…'|url }}`. Quiet
does. A Theme that writes `/assets/…` directly fails the build with
`LINK_OUTSIDE_SITE`, which names the fix.

## Featured writing on Home

Featured posts are an option of Quiet, not a site field:

```yaml
theme:
  options:
    featured_posts: [41, 62, 49]
    tagline: I make tools for the way I work.
profile:
  bio: Practical notes from building and using those tools.
```

`featured_posts` lists Blog Issue numbers in the order you want them. The
numbers must be unique positive integers. A number that is not a published
Blog post is left out with the warning `THEME_OPTION_POST_MISSING`; the build
still publishes. Titles, dates and links come from the posts themselves.
Featuring a post changes nothing else: archives, the feed and labels stay the
same. Without featured posts, Quiet shows only recent writing.

Quiet's Home is one centered column: the tagline and bio, links to Blog,
Projects and About, then Featured (when set), Recent Articles (up to five,
newest first, may repeat a featured post) and up to four featured projects.
Both writing lists show only titles and dates. The Blog archive at `/blog/`
also shows each post's description and tags. See [Quiet](themes/quiet.md) for
the rest of its layout.

Any Theme can declare its own option of type `posts`; it receives the
matching Blog posts in the listed order.

## About

An explicit `about.issue_number` must be a published About Issue by an allowed
author. If it is missing, unpublished, a Pull Request or of another type, the
build fails. Without a number, the oldest published About Issue is used; any
other published About Issue is skipped and reported.

With no About Issue, the About page shows the profile: the author name and
the bio (or the site description). This Profile About has no Issue number, no
date and no comments; its body is the bio. Themes tell the two apart with
`is_profile`; see the [Theme guide](themes/authoring.md#content-models).
`pages.about: false` removes the About page.

## Selected Projects

```yaml
projects:
  - repository: alice/tool              # title and summary come from GitHub
  - repository: alice/other
    title: My title
    summary: ""                         # an explicit empty summary is kept
    image: https://raw.githubusercontent.com/alice/other/<commit-sha>/preview.webp
    links:
      - name: Demo
        url: https://demo.example.com/
  - website: https://example.com/       # a project without a repository
    slug: example
    title: Example
```

Each project needs a `repository`, a `website`, or both. `slug` defaults to the
repository name in kebab case (`alice/My_Tool` → `my-tool`); a project without
a repository must set `slug` and `title`. Slugs must be unique. The slug can
name one page per project, for example `pages.extra` with
`for_each: projects` at `/projects/{slug}/` (see [Pages](#pages)).

Only the listed repositories are read from GitHub. A missing title or summary
uses the repository's name or description; values you set win, including an
empty summary. If GitHub cannot be read, the project is kept with a warning and
uses `fallback_metadata`. A renamed repository never changes the configured
repository, slug or links.

`image` must be an HTTPS URL or a root-relative file the Theme publishes, such
as `/assets/images/project.webp`. Prefer HTTPS links pinned to a commit.
`links` are named links with safe URLs. `featured: true` shows a project on
Quiet's Home and About; `order` sorts the list.

## Config roots and the Site Orchestrator

The output directory and a local Theme path are relative to the directory that
holds the Config file, never to the current directory or the context file.
Do not copy the Config elsewhere to resolve defaults.

Automation that needs the token variable name can reuse the same parser:

```python
from pathlib import Path
from escaping.config import read_config_overrides, security_from_config

overrides = read_config_overrides(Path("site/config.yaml"))
token_env = security_from_config(overrides).token_env
```

This returns only the validated name. The CLI reads the token from that
variable; no token belongs in JSON, arguments, logs or the output.
