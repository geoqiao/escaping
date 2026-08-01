---
name: issue-draft-uploader
description: Validate one Local Draft and upload it as a new unpublished GitHub Issue with its type and tag labels.
disable-model-invocation: true
---

# Issue Draft Uploader

Upload exactly one Local Draft as exactly one new, unpublished GitHub Issue.
This is a one-way create operation, not synchronization.

## Invocation

```text
/skill:issue-draft-uploader <draft-path> <owner/repo>
```

Both arguments are required. If either is missing or the target repository is
ambiguous, ask the user before performing any GitHub mutation.

## Procedure

1. Read `../../../docs/contracts/local-draft-v1.md` completely.
2. Read the Local Draft without modifying it.
3. Parse its YAML front matter with a safe YAML loader and reject duplicate
   keys, custom YAML tags, malformed YAML, unknown fields, or a missing closing
   delimiter.
4. Validate every field and the Markdown body against the Local Draft Contract.
   Stop before any GitHub mutation if validation fails; report every validation
   error with its field name.
5. Build a temporary Issue body:
   - copy `slug` when present;
   - copy `description` and `created_date`;
   - omit local-only `title`, `type`, and `tags`;
   - append the Markdown body unchanged.
6. Build labels from the validated draft:
   - `type` becomes exactly one `type:<value>` label;
   - every item in Blog or Idea `tags` becomes one `tag:<value>` label;
   - do not add `published`.
7. Run `gh auth status`. If authentication is unavailable, ask the user to run
   `gh auth login`; never request or persist a password, token, cookie, or other
   credential.
8. Confirm the target repository exists. List its labels and create every
   missing required label before creating the Issue:
   - create missing `type:*` labels with color `D4C5F9`;
   - create missing `tag:*` labels with color `C2E0C6`;
   - never use `--force` or alter an existing label.
9. Create the Issue with one `gh issue create` command using the explicit
   `--repo`, validated title, temporary body file, and all type/tag labels.
10. Delete the temporary body file. Report the created Issue number, URL, type
    label, and tag labels.

## Mutation safety

The invocation authorizes creation of missing required labels and one Issue in
the explicit target repository. Never update an existing Issue or label, write
upload state, modify the Local Draft, create a sidecar, add `published`, or
retry automatically after an ambiguous network failure. If the command may have created an Issue but did not return a
clear result, inspect the target repository and ask the user before retrying.

## Completion criterion

Complete only when validation passed, every required label exists, one Issue
was created in the explicit target repository with every required type/tag
label, and its number and URL were reported. A validation, authentication,
repository, label, or creation failure is a failed upload and must be reported
without claiming success.
