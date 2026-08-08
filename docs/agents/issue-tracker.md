# Issue tracker: GitHub

本仓库的 issues 与 specs 使用 GitHub Issues 管理。使用 `gh` CLI 在当前 clone
中执行操作，仓库由 `origin` remote 自动推断。

## Conventions

- 创建：`gh issue create --title "..." --body "..."`
- 读取：`gh issue view <number> --comments`
- 列出：`gh issue list --state open`
- 评论：`gh issue comment <number> --body "..."`
- 标签：`gh issue edit <number> --add-label "..."` 或 `--remove-label "..."`
- 关闭：`gh issue close <number> --comment "..."`

PRs 不作为 triage 请求入口。

## When a skill says "publish to the issue tracker"

创建 GitHub Issue。

## When a skill says "fetch the relevant ticket"

运行 `gh issue view <number> --comments`。

## Wayfinding operations

`/wayfinder` 使用一个带有 `wayfinder:map` 标签的 GitHub Issue 作为 map，并将
child tickets 作为子 Issue。优先使用 GitHub 原生 issue dependencies 表示阻塞关系；
不可用时在 child body 顶部记录 `Blocked by: #<n>, #<n>`。
