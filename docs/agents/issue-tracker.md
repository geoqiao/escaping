# Issue tracker: Local Markdown

本仓库的 issues 与 specs（也称 PRD）使用 `.scratch/` 下的 Markdown 文件管理。

## Conventions

- 每个 feature 使用独立目录：`.scratch/<feature-slug>/`
- Feature spec 位于 `.scratch/<feature-slug>/spec.md`
- 每个 implementation ticket 使用单独文件：`.scratch/<feature-slug>/issues/<NN>-<slug>.md`
- Ticket 从 `01` 开始编号，不得合并为单一 tickets 文件
- Triage 状态记录在 ticket 文件顶部附近的 `Status:` 字段中
- Triage role 字符串见 `docs/agents/triage-labels.md`
- 评论与讨论记录追加到文件底部的 `## Comments` 章节

## When a skill says "publish to the issue tracker"

在 `.scratch/<feature-slug>/` 下创建 Markdown 文件；目录不存在时一并创建。

## When a skill says "fetch the relevant ticket"

读取用户指定路径或编号对应的 ticket 文件。

## Wayfinding operations

`/wayfinder` 使用一个 map 文件和每个 ticket 对应的 child 文件：

- Map：`.scratch/<effort>/map.md`
- Child ticket：`.scratch/<effort>/issues/NN-<slug>.md`
- `Type:` 记录 ticket 类型：`research`、`prototype`、`grilling` 或 `task`
- `Status:` 记录 `claimed` 或 `resolved`
- `Blocked by: NN, NN` 记录依赖；列出的 ticket 全部为 `resolved` 后，当前 ticket 才解除阻塞
- Frontier：扫描开放、未阻塞且未认领的 ticket，编号最小者优先
- Claim：开始工作前将 `Status:` 改为 `claimed` 并保存
- Resolve：在 `## Answer` 下追加结果，将状态改为 `resolved`，
  再向 `map.md` 的 Decisions-so-far 添加摘要与上下文链接
