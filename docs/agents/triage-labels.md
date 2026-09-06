# Triage Labels

Engineering skills 使用五个 canonical triage roles。
下表定义本仓库的标签命名约定，不表示这些标签已在 GitHub 全部创建。
这些是维护任务标签，与站点内容的 `published` / `type:*` / `tag:*` 标签不同。

| Canonical role    | Tracker string    | 含义                     |
| ----------------- | ----------------- | ------------------------ |
| `needs-triage`    | `needs-triage`    | 等待维护者评估           |
| `needs-info`      | `needs-info`      | 等待报告者补充信息       |
| `ready-for-agent` | `ready-for-agent` | 已充分定义，可交给 Agent |
| `ready-for-human` | `ready-for-human` | 需要人工实施             |
| `wontfix`         | `wontfix`         | 不会实施                 |

当 skill 提及某个 canonical role 时，使用相应约定名称。操作前运行
`gh label list --limit 100` 检查现存标签（更多结果需继续获取）；缺失时报告，
仅在获得相应授权后创建，不替换为含义不同的标签，也不改写已有颜色或描述。
文档整理或只读检查本身不授权远程写入。
