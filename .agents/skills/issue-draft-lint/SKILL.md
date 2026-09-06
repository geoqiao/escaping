---
name: issue-draft-lint
description: Read-only, optional Local Draft validation and attachment advice; never upload or publish.
disable-model-invocation: true
---

# Issue Draft Lint

Check one draft only when the user asks. Authors can instead write a legal Issue
in GitHub directly; neither this skill nor lint is a CI publication review.

## Invocation

```text
/skill:issue-draft-lint <draft-path>
```

If the path is missing or ambiguous, ask. Read
`../../../docs/contracts/local-draft-v1.md` and
`../../../docs/contracts/issue-content-v1.md`. Paths are relative to this skill.

## Deterministic check

Use an environment containing the reviewed `escpe` package, then run:

```text
python -m escaping.local_draft <draft-path>
```

Pass the path as one argument, not interpolated shell code. This real module is
read-only: exit 0 emits JSON with `issue` (title, body, labels) and an empty
`diagnostics` list; exit 1 emits `issue: null` and field/code/message diagnostics.
A missing module is an unavailable check, not permission to recreate validation
in agent prose, a YAML snippet, or a second script. Report failure honestly.

The module reuses the compiler's YAML, authored metadata and sanitized GFM rules.
Report its diagnostics, without replacing explicit invalid values with guesses.
Suggest metadata overrides only on request, as a reviewable proposal that can be
adopted field by field. Missing slug, description and creation date stay missing:
there is no future Issue number/date to infer. The result contains an empty
mapping envelope when needed to keep a body's leading `---` as body content.
Do not replace Markdown with the sanitizer's HTML or rewrite links or formatting.

This check does not prove author eligibility, collection-wide route uniqueness,
publication history, external resource availability or deployability. It does
not create an Issue. Do not invoke gh, authentication, the uploader or a build.
Do not write the draft, a sidecar, upload state, commit, push, or add `published`.

For an already published article, offer review-only advice and preserve its
existing slug. Do not turn it into a new Local Draft/upload or manufacture a
snapshot to run the compiler. Without its real inputs, do not claim a deterministic
Issue check or historical slug verification. Existing-Issue editing/migration is
outside this skill and needs separate authorization.

## Optional attachment inspection

Only inspect explicitly requested local files or already-public HTTPS resources;
validation does not automatically fetch URLs. A local attachment path is not an
upload instruction, and GitHub-native attachments are external links, not files
automatically copied to Pages.

| Evidence | Minimal check and honest result |
| --- | --- |
| Local bytes | Use `Path.stat().st_size` and `hashlib.sha256(Path.read_bytes())` on the explicit original; do not modify it. Record the absolute path and hash. |
| MIME | If available, `file --brief --mime-type <absolute-path>` identifies bytes. Filename `mimetypes` inference and HTTP Content-Type are **declared**, not verified byte format. If unsupported, say unknown. |
| Dimensions | If available, use read-only `sips -g pixelWidth -g pixelHeight <absolute-path>` or installed ImageMagick identify. Tool failure/absence means unknown. Do not install image dependencies or write a PNG/JPEG parser. |
| alt / HTML dimensions | Inspect the author's Markdown, or use `parse_yaml_envelope` and shared `content_validation.render_body`, then stdlib `HTMLParser` to read img attributes. Label HTML width/height as declared, not intrinsic. Missing alt and deliberately empty decorative alt differ; a non-empty value alone does not prove useful alternative text. |
| Public URL | On a separately requested public-resource check, use a bounded read-only request without credentials (for example curl with timeout and max-size). Inspect redirects before following, never follow into private/local networks. Record final URL/status, actual downloaded byte count/hash and declared Content-Type. A HEAD response or 200 alone does not verify the image bytes or permanence. No automatic mirror/upload on failure. |
| Root-relative URL | Require the identified final artifact/document root, exact path/case and output-chain evidence. Repository file existence is not deployment proof. Current Theme assets are copied under `/templates/<name>/static/`; arbitrary `/assets/` has no automatic import step. Do not ban that prefix categorically, invent a copy step, follow escaping symlinks, or weaken the validator. If evidence is absent, report unproven, not deployable. |

Prefer already-existing, readable full-commit HTTPS attachment URLs where
appropriate; a moving branch URL is not immutable. Do not invent an unpublished
commit URL. Check capabilities before claiming any result. Do not run converters,
optimizers or installers during lint.

If a user later authorizes preparing an optimized copy, first specify original
input → distinct output path and proposed URL/diff. Keep the original and its
hash; report the new bytes/MIME/dimensions and show the exact reference changes
for review. This does not authorize commit/push, editing an Issue or publication.
Never overwrite an existing attachment or change a published slug as cleanup.
Existing attachments, body text and fonts are not implicit optimization targets.

## Completion

Report validation success/failure separately from optional suggestions and
attachment evidence/unknowns. A successful lint is not an upload or release.
