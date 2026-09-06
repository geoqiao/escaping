# Site inputs: defaults and explicit overrides

The CLI resolves missing Config fields once, before compilation. The renderer,
artifact validator, and `Settings` constructors never fetch public profiles.
Direct `Settings` injection remains supported without new Profile requests.

Use the [starter instructions](../starter/README.md) for the normal hosted workflow.
This document owns Config sources and resolution; rendering, comments and Theme
migration belong to the [Theme API 2 guide](themes/authoring.md).

## CLI inputs

Without platform context, supply at least an actual content repository and the
actual HTTPS root URL (not a guessed Pages URL):

```yaml
github:
  repo: alice/site
site:
  url: https://notes.example/
```

The CLI verifies the repository owner through GitHub. Organizations must also
supply `github.allowed_authors`. Complete explicit identity/Profile settings
need neither context nor Profile enrichment. [config.example.yaml](../config.example.yaml)
is the expanded reference, not a list of mandatory fields.

An orchestrator may instead provide `config.yaml` containing `{}` and an
independently verified, non-secret platform snapshot:

```json
{
  "repository": "alice/site",
  "owner_login": "alice",
  "owner_type": "User",
  "pages_base_url": "https://notes.example/",
  "pages_base_path": "/"
}
```

```bash
escpe --config /path/to/site/config.yaml --context /path/to/context.json
```

Context has exactly these five required fields. Only GitHub.com User or
Organization owners and HTTPS root Pages URLs are supported. The repository
owner and `owner_login` must agree (case-insensitively). No actor, email, token,
Config overrides, project-site subpath, userinfo, query, or fragment belongs in
context. Duplicate/unknown fields and invalid values fail even when Config has a
valid URL. The orchestrator must verify the repository and actual Pages
configuration; this JSON is a platform snapshot, not an alternative Site Config
or a way for Issue content to grant publishing permission.

`--repo owner/repo` remains an explicit repository override. Both this option and
a Config repository differing from context require fresh repository identity
verification. Pages origin still belongs to the site context unless Config
explicitly overrides it. A repository redirect/rename cannot silently authorize
a different content repository; update Config deliberately.

## Local build

Local source builds require Python 3.14.x, [uv](https://docs.astral.sh/uv/) and a
GitHub token that can read the target repository's Issues. Clone the generator
and prepare a separate site directory:

```bash
git clone https://github.com/geoqiao/escaping.git
cd escaping
uv sync --locked
mkdir -p ../my-site
```

Save the minimal YAML from [CLI inputs](#cli-inputs) as `../my-site/config.yaml`,
using your actual repository and HTTPS root URL. Add `github.allowed_authors`
for an Organization. Then build and preview:

```bash
export GITHUB_TOKEN=...
uv run escpe --config ../my-site/config.yaml
uv run python -m http.server 8000 --directory ../my-site/output
```

Open <http://localhost:8000>. This example uses the default output directory;
serve your resolved output as the HTTP document root, never under an `/output/`
URL prefix. `security.token_env` selects the token variable name if changed.
This is local generation, not production deployment; locked production source
installation follows the [deployment contract](deployment.md#locked-source-installation).

## Missing-field sources

| Config field | Source when absent |
| --- | --- |
| `github.repo` | Validated context repository; otherwise required explicitly |
| `github.allowed_authors` | Verified User owner login, never actor; Organization requires an explicit list |
| `site.url` | Actual root Pages URL in context; otherwise required explicitly |
| `site.title`, `site.author` | Public owner `name` (trimmed), otherwise verified owner login |
| `site.description` | Public owner `bio`, otherwise empty |
| `profile.avatar`, `profile.bio` | Public `avatar_url` / `bio`, otherwise empty |
| `security.token_env` | `GITHUB_TOKEN` (the variable name, not a token) |
| `about.issue_number` | Discover the sole valid published About Issue; otherwise Profile About |
| `projects` | Empty list; never enumerate an owner's repositories |
| `theme` | Built-in Quiet |
| `site.navigation.items` | Home `/`, Blog `/blog/`, Projects `/projects/`, Tags `/tags/`, About `/about/`, RSS `/atom.xml` |
| `comments.enabled` | `false`; only actual YAML booleans are accepted |
| Other fields | Existing strict model defaults, including output `output` and page size 10 |

The default menu omits Ideas; an explicit `site.navigation.items` list may still
include `/ideas/`, and Idea routes and format remain supported.

Only absent fields get defaults. Explicit legal empty strings, `false`, and
empty lists survive. Nested objects resolve field by field; lists replace as a
whole. Null, unknown fields, unsafe URLs, duplicate YAML keys, and other invalid
explicit values fail, not fall back. The existing `comments.repo: ""` content
repository fallback is unchanged. Author entries are trimmed; this does not
expand the authorization set. Only missing repository/site identity fields can
be deferred to context/Profile resolution. Selected project `repository`, link
`name`/`url`, and local Theme `name`/`path` must be supplied before any API request.

Only public `login/name/avatar_url/bio` are fetched for Profile defaults. Optional
Profile failure emits `PROFILE_ENRICHMENT_FAILED`, then uses the verified owner
login and empty avatar/bio. Necessary repository identity and Issue failures
stop the build and preserve old output. Exception payloads are not used as
public diagnostics. There is no PAT fallback, remote write, or Profile fetch
inside an Issue loop.

## About and local Themes

An explicit `about.issue_number` wins and must identify valid, allowed-author,
published About content. Missing, unauthorized, draft, PR, wrong-type or invalid
selected Issues fail. Without a selection, the sole valid published About is
used; multiple candidates fail rather than selecting the latest. Invalid
published content still fails the whole build.

With no About Issue, `SiteBuilder` creates a distinct immutable `ProfileAbout`
using resolved author/bio and the registered `/about/` Route. It has no Issue
identity, authored date, body HTML or discussion thread; it is not a fake Issue.

Local Themes must declare API `"2"` and handle both About variants. Exact fields,
autoescape, comments and JSON-LD rules have one source of truth: the
[Theme About contract](themes/authoring.md#about-branch-before-reading-issue-only-fields).
API 1 fails clearly and preserves old output; changing only the version string
is not a migration. Follow the [migration checklist](themes/authoring.md#migrating-from-api-1).

## Selected Projects

```yaml
projects:
  - repository: Alice/Tool
    image: https://raw.githubusercontent.com/Alice/Tool/<commit-sha>/preview.webp
    links:
      - name: Demo
        url: https://demo.example.com/
  - repository: Bob/Tool
    title: My title
    summary: ""
```

`image` defaults to `""` and `links` to `[]`. Images use the existing safe
resource URL validation: prefer HTTPS URLs pinned to an immutable commit. A
root-relative image must already be a file under the selected Theme asset path,
for example `/templates/my-theme/static/images/project.webp`; arbitrary
`/assets/...` paths are not copied or registered by the generator. Named links
use the existing safe `Link` contract and are exposed as immutable values with
`.name` and `.url`.

A missing `slug` is the complete configured `repository.casefold()`:
`alice/tool` and `bob/tool` are distinct. It is an internal catalog key, **not**
a Route or an article slug. Explicit keys keep their spelling; exact duplicate
final keys fail. To preserve a key when deliberately changing the configured
repository, supply the old key explicitly.

Only selected repositories are enriched. Missing title/summary use public
repository name/description; explicit values (including empty summary) win.
Optional API failure warns and keeps the project, using the configured repo's
last segment, empty summary, and existing `fallback_metadata`. API rename data
cannot change configured identity, key, or link. Repeated repo requests may be
reused within one batch; there is no persistent project ledger.

## Config roots and Site Orchestrator interface

Output and local Theme paths always belong to the **original Config directory**,
not the context directory or process CWD. Never copy Config to a temporary
platform directory just to resolve defaults.

The Site Orchestrator can use the same safe parser and security validation
before final Settings:

```python
from pathlib import Path
from escaping.config import read_config_overrides, security_from_config

overrides = read_config_overrides(Path("site/config.yaml"))
token_env = security_from_config(overrides).token_env
```

This returns a validated name only and does not mutate the process environment.
CLI reads the value from that environment variable; no secret belongs in JSON,
argv, logs, or artifacts. An Orchestrator that maps secrets into a child process
owns reserved environment-name and collision checks. Reuse this parser rather
than `eval` or an alternative YAML loader. Keep the original overrides mapping
when absence matters. `model_dump(exclude_unset=True)` preserves omitted model
defaults only for a model constructed directly from that input; it cannot recover
original YAML provenance from resolved `Settings`, where context/Profile values
have already been supplied. Serializing resolved values as overrides freezes them.
