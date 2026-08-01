# Triage Labels

Engineering skills 使用五个 canonical triage roles。
下表定义本仓库 Local Markdown tracker 使用的实际字符串。

| Canonical role    | Tracker string    | 含义                     |
| ----------------- | ----------------- | ------------------------ |
| `needs-triage`    | `needs-triage`    | 等待维护者评估           |
| `needs-info`      | `needs-info`      | 等待报告者补充信息       |
| `ready-for-agent` | `ready-for-agent` | 已充分定义，可交给 Agent |
| `ready-for-human` | `ready-for-human` | 需要人工实施             |
| `wontfix`         | `wontfix`         | 不会实施                 |

当 skill 提及某个 canonical role 时，在 ticket 的 `Status:` 字段中使用对应的 tracker string。
