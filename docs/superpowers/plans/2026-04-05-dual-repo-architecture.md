# Dual Repository Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure escaping as the sole code repository, with geoqiao.github.io only handling issues and receiving workflow updates via sync.

**Architecture:** All source code, workflows, and templates live in escaping. A sync.yml workflow detects changes to trigger.yml and pushes to geoqiao.github.io. When geoqiao.github.io issues are updated, trigger.yml sends a repository_dispatch event to escaping, which then generates and deploys the site.

**Tech Stack:** GitHub Actions, GitHub API (repository_dispatch), curl

---

## Background

**Current State:**
- Local code is pushed to geoqiao.github.io (not escaping)
- escaping has not been updated for a long time
- Code maintenance is fragmented

**Target State:**
- escaping is the single source of truth for all code
- geoqiao.github.io stores issues (blog content) and receives workflow sync
- Issues update → automatic trigger → escaping generates and deploys

**Token Status:** G_T already added to both repositories ✅

---

## Repository Responsibilities

| Repository | Role | Contents |
|-----------|------|----------|
| `escaping` | Main development repository | Source code, workflows (gen_site.yml, sync.yml, trigger.yml) |
| `geoqiao.github.io` | Issues + GitHub Pages | Issues (blog posts), trigger.yml (received via sync) |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ escaping (sole code repository)                         │
│                                                             │
│ ├── .github/workflows/                                     │
│ │   ├── gen_site.yml     ✅ Runs here                      │
│ │   ├── trigger.yml     ❌ Only synced, doesn't run here   │
│ │   └── sync.yml        ✅ Detects trigger.yml changes     │
│ │                         and pushes to geoqiao.github.io  │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ sync.yml (on trigger.yml change)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ geoqiao.github.io (issues + GitHub Pages)                   │
│                                                             │
│ ├── Issues (blog posts)                                    │
│ └── .github/workflows/                                      │
│     └── trigger.yml     ✅ Received via sync                │
│                           ✅ Runs here, detects issue       │
│                           events and sends dispatch         │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ repository_dispatch
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ escaping (receives dispatch)                            │
│                                                             │
│ gen_site.yml runs:                                         │
│   1. Reads geoqiao.github.io issues                         │
│   2. Generates static site                                 │
│   3. Deploys to GitHub Pages (geoqiao.github.io)          │
└─────────────────────────────────────────────────────────────┘
```

---

## File Change Summary

| Action | File | Description |
|--------|------|-------------|
| Modify | `.github/workflows/gen_site.yml` | Add repository_dispatch trigger |
| Create | `.github/workflows/sync.yml` | Sync trigger.yml to geoqiao.github.io |
| Create | `.github/workflows/trigger.yml` | Listen to issues, send dispatch (escaping only maintains) |

**No changes to:** src/, templates/, config.yaml, tests/

---

## Task 1: Modify gen_site.yml - Add repository_dispatch Trigger

**Files:**
- Modify: `.github/workflows/gen_site.yml`

- [ ] **Step 1: Read current gen_site.yml**

```bash
cat .github/workflows/gen_site.yml
```

- [ ] **Step 2: Add repository_dispatch to triggers**

Current triggers:
```yaml
on:
  workflow_dispatch:
  push:
    branches:
      - main
```

New triggers:
```yaml
on:
  workflow_dispatch:
  repository_dispatch:
    types: [issue_update]
  push:
    branches:
      - main
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/gen_site.yml
git commit -m "feat(ci): add repository_dispatch trigger for issue_update events"
```

---

## Task 2: Create sync.yml - Sync trigger.yml to geoqiao.github.io

**Files:**
- Create: `.github/workflows/sync.yml`

- [ ] **Step 1: Create sync.yml with proper triggers to avoid race condition**

```yaml
name: Sync Trigger to Geoqiao Pages

on:
  push:
    paths:
      - '.github/workflows/trigger.yml'
    branches:
      - main

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Push trigger.yml to geoqiao.github.io
        env:
          GH_TOKEN: ${{ secrets.G_T }}
        run: |
          # Clone geoqiao.github.io
          git clone https://github.com/geoqiao/geoqiao.github.io.git _pages

          # Copy trigger.yml
          mkdir -p _pages/.github/workflows
          cp .github/workflows/trigger.yml _pages/.github/workflows/

          # Commit and push
          cd _pages
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add .
          git commit -m "sync: update trigger.yml from escaping"
          git push --force-with-lease
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/sync.yml
git commit -m "feat(ci): add sync.yml to push trigger.yml to geoqiao.github.io"
```

---

## Task 3: Create trigger.yml - Issue Events to Dispatch

**Files:**
- Create: `.github/workflows/trigger.yml`

- [ ] **Step 1: Create trigger.yml**

```yaml
name: Trigger Deploy

on:
  issues:
    types: [opened, edited]
  issue_comment:
    types: [created, edited]

jobs:
  trigger:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger escaping
        env:
          GH_TOKEN: ${{ secrets.G_T }}
        run: |
          curl -L -X POST \
            -H "Accept: application/vnd.github+json" \
            -H "Authorization: Bearer $GH_TOKEN" \
            -H "X-GitHub-Api-Version: 2022-11-28" \
            https://api.github.com/repos/geoqiao/escaping/dispatches \
            -d '{"event_type":"issue_update"}'
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/trigger.yml
git commit -m "feat(ci): add trigger.yml for issue events"
```

---

## Task 4: Initial Sync trigger.yml to geoqiao.github.io

- [ ] **Step 1: Manually trigger sync.yml**

Go to GitHub → escaping → Actions → "Sync Trigger to Geoqiao Pages" → Run workflow

Or push an empty commit to trigger:

```bash
git commit --allow-empty -m "chore: trigger initial sync"
git push origin main
```

- [ ] **Step 2: Verify geoqiao.github.io has trigger.yml**

Check: https://github.com/geoqiao/geoqiao.github.io/blob/main/.github/workflows/trigger.yml

---

## Task 5: Update Local Git Remote

**Files:**
- Modify: `.git/config` (local only, not committed)

- [ ] **Step 1: Check current remote**

```bash
git remote -v
```

Expected output:
```
origin  git@github.com:geoqiao/geoqiao.github.io.git (push)
```

- [ ] **Step 2: Change remote to escaping**

```bash
git remote set-url origin git@github.com:geoqiao/escaping.git
```

- [ ] **Step 3: Verify new remote**

```bash
git remote -v
```

Expected output:
```
origin  git@github.com:geoqiao/escaping.git (push)
```

- [ ] **Step 4: Push to escaping (local repo is source of truth)**

```bash
git push origin main --force
```

Note: escaping has been out of sync for a long time. `--force` ensures local code overwrites remote completely.

---

## Task 6: Verification

- [ ] **Step 1: Verify escaping workflows exist**

Check: https://github.com/geoqiao/escaping/actions

Should see:
- Generate Github_blog site
- Sync Trigger to Geoqiao Pages

- [ ] **Step 2: Verify geoqiao.github.io trigger.yml synced**

Check: https://github.com/geoqiao/geoqiao.github.io/blob/main/.github/workflows/trigger.yml

- [ ] **Step 3: Test issue update trigger**

Create or edit an issue in geoqiao.github.io and verify:
1. trigger.yml runs in geoqiao.github.io
2. dispatch sent to escaping
3. gen_site.yml runs in escaping
4. site deployed to GitHub Pages

---

## Verification Commands

```bash
# Check current remote
git remote -v

# Check escaping workflows exist
# https://github.com/geoqiao/escaping/actions

# Check geoqiao.github.io trigger.yml
# https://github.com/geoqiao/geoqiao.github.io/blob/main/.github/workflows/trigger.yml

# Verify deployment
# https://geoqiao.github.io
```

---

## Rollback Plan

If something goes wrong:

1. **If geoqiao.github.io trigger.yml is broken:**
   - Manually edit trigger.yml directly in geoqiao.github.io
   - Or disable the workflow in geoqiao.github.io Actions

2. **If escaping gen_site.yml fails:**
   - Check Actions logs for errors
   - Use workflow_dispatch for manual trigger

3. **If sync.yml fails:**
   - Manually copy trigger.yml to geoqiao.github.io
   - Or run sync.yml manually from GitHub Actions UI

---

## Self-Review Checklist

- [ ] **Spec coverage:** All 3 workflows (gen_site.yml, sync.yml, trigger.yml) have tasks
- [ ] **No placeholders:** All workflow YAML is complete, no TODOs
- [ ] **Type consistency:** All references to G_T use `secrets.G_T`
- [ ] **Token verified:** G_T exists in both repositories (user confirmed)
- [ ] **Permissions verified:** gen_site.yml has pages: write (current config confirmed)
- [ ] **Race condition addressed:** sync.yml only triggers on trigger.yml path changes
- [ ] **Local remote change documented:** Not committed, just local configuration
