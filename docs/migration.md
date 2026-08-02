# Strict Site Compiler migration

The feature branch uses one strict pipeline. It reads the Issue Content v1
contract, builds a `SiteModel`, resolves every URL through one
`RouteRegistry`, validates the complete Pages artifact, and publishes it
atomically.

## Configuration

Use the same shape as `config.example.yaml`:

```yaml
github:
  repo: username/username.github.io
  allowed_authors: [username]
site:
  title: "Blog Title"
  url: https://geoqiao.me/
  author: "Your Name"
  description: "A short description"
  language: en
  navigation:
    items:
      - {name: Blog, url: /blog/}
      - {name: Ideas, url: /ideas/}
      - {name: Projects, url: /projects/}
      - {name: Tags, url: /tags/}
      - {name: About, url: /about/}
profile:
  avatar: https://github.com/username.png
  bio: "A short bio"
  links:
    - {name: GitHub, url: https://github.com/username}
about:
  issue_number: 1
paths:
  output: output
  theme: geoqiao.me
  page_size: 10
theme_lock:
  repository: geoqiao/escaping
  commit: <full-40-character-commit-sha>
  api_version: "1"
comments:
  provider: utterances
  repo: ""
  theme: github-light
  theme_mode: auto
security:
  token_env: GITHUB_TOKEN
```

`paths` only controls the output directory, locked theme name, and page size.
Blog, Idea, About, Projects, Tags, Atom, sitemap, and robots paths are fixed
by `RouteRegistry`; they are not configurable URL fragments.

## Issue Content

Published Issues must follow `docs/contracts/issue-content-v1.md`:

- exactly one `type:blog`, `type:idea`, or `type:about` label;
- Blog front matter requires a lower-case kebab-case `slug`, `description`, and
  quoted `created_date`;
- Idea and About content cannot define a slug;
- the configured About Issue must be the single published `type:about` Issue;
- body HTML is rendered and sanitized before it reaches templates.

Unpublished Issues, Pull Requests, and unauthorized authors are ignored unless
that would make the configured About Issue invalid. There is no compatibility
parser or second content pipeline.

## Local verification

```bash
export GITHUB_TOKEN=ghp_xxxxx
uv run blog-gen
uv run python -m http.server 8000 --directory output
uv run pytest -q
uv run ruff check src/github_blog tests
uv run ruff format --check src/github_blog tests
uv run ty check
```

The generated site uses directory-index routes such as `/blog/example/` and
`/about/`. Old URL forms are not aliases or redirects; the accepted decision is
recorded in `docs/adr/0003-drop-legacy-html-urls.md`.

Utterances keeps Issue-number bindings. With `comments.theme_mode: auto`, the
shared comment include follows the blog theme with `postMessage` and
`MutationObserver`, and retains the Safari lazy-iframe workaround.
