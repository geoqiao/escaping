# AGENTS.md

本文件是 `escaping` 仓库的 coding-agent 指南。以当前代码、测试和 domain docs 为准。
架构与完整文档导航见[维护者入口](docs/dual-repo-architecture.md)，当前边界见
[ADR-0013](docs/adr/0013-escaping-exports-markdown-the-site-renders.md)。

## 产品与边界

`escaping` 只做一件事：把一个仓库里已发布的 GitHub Issue 写成 Markdown 文件和一份
manifest（`escaping-site export`）。

- `escaping` 负责：读取 Issue、决定哪些发布、应用内容规则、解析每个值、写文件、
  安全地替换导出目录。
- 站点负责：渲染 Markdown 及其安全、网址、分页、feed、sitemap、搜索、评论、外观和部署。
  主题就是读导出文件的站点代码，本仓库里没有任何主题。
- 默认主题在 [escaping-template](https://github.com/geoqiao/escaping-template) 仓库，
  它和用户自己写的站点一样只依赖 [Content Export v1](docs/contracts/content-export-v1.md)。
- 站点仓库 pin PyPI 上的 `escaping-site@X.Y.Z`（打 tag 时由
  `.github/workflows/release.yml` 发布）；workflow 使用短期 `GITHUB_TOKEN`，不得硬编码 PAT。

Issue 是唯一内容来源，`published` 标签控制发布，内容类型只有 Blog、Idea、About。
不要把渲染、网址、主题或任何站点设置加回本仓库；改变这些边界需单独确认。

## 按任务读取

探索代码前先读 [CONTEXT.md](CONTEXT.md) 和相关 [ADR](docs/adr/)，其余按需读取。

| 任务 | 文档 |
| --- | --- |
| 内容与发布规则 | [Issue Content v1](docs/contracts/issue-content-v1.md) |
| 导出的文件、manifest、命令与 Config | [Content Export v1](docs/contracts/content-export-v1.md) |
| 为什么只有导出 | [ADR-0013](docs/adr/0013-escaping-exports-markdown-the-site-renders.md)、[ADR-0011](docs/adr/0011-content-export-for-sites-built-elsewhere.md) |
| 可选草稿创作辅助 | [Local Draft v1](docs/contracts/local-draft-v1.md)，不用于同步或发布 |
| 开发与验证 | [测试策略](docs/agents/testing.md) |
| workflow、版本与发布 | [Deployment](docs/deployment.md) |
| Issues 与 specs | [GitHub tracker](docs/agents/issue-tracker.md)、[triage 标签约定](docs/agents/triage-labels.md)；使用前检查标签是否存在 |
| Domain 文档维护 | [single-context 约定](docs/agents/domain.md) |

## 关键实现约束

1. **Config 只有三段**：`github`、`about`、`security`。这三段里未知字段报错；文件里的
   其他段属于站点，不读也不检查。不得为某个站点或主题加字段。
2. **内核不知道站点。** `issue_content.py` 决定哪些 Issue 发布、每个值是什么；它不知道
   网址、页面和外观。
3. **导出是确定的。** 同样的 Issue 和 Config 得到逐字节相同的文件，不写入导出时间；
   提交导出目录的 workflow 依赖这一点。
4. **导出前先检查本地输入。** Config 和导出目录安全在读取 Issue 之前完成；这些错误让
   导出直接失败，不产生半成品。
5. **错误按范围处理。** 单个 Blog/Idea Issue 的内容错误只跳过该 Issue，报告 Issue
   编号，照常导出其余内容，CLI 以状态码 2 结束。Config 和 About 选择的错误属于整体
   错误，不写任何文件，上一次导出原样保留。
6. Config 中的相对路径和 `--output` 以 Config 文件所在目录为根，不依赖 CWD。
7. 正文在导出时仍会渲染并净化一次，只为拒绝无法渲染的正文和推导默认摘要；导出的
   正文是作者的 Markdown 原文，不是净化后的 HTML。
8. 不得弱化 output containment、导出目录归属检查或 staged output publication；
   目录里有不是本工具写的文件时拒绝覆盖。
9. 错误信息说明位置和原因，不回显字段值（可能含敏感信息）。GitHub Token 环境变量名
   由 `security.token_env` 决定；异常文本不得原样输出。

## 当前结构

```text
src/escaping_site/
├── cli.py                 # escaping-site export
├── config.py              # github / about / security 三段
├── content_inputs.py      # 补全 Config 缺省值（仓库、作者）
├── issue_content.py       # 内容内核：Issue → 条目，坏 Issue 跳过
├── content_validation.py  # Issue 与本地草稿共用的内容规则、Markdown 渲染
├── content_export.py      # 条目写成 Markdown + manifest
├── output_safety.py       # 导出目录不越界
├── output_staging.py      # 先写临时目录，成功后替换；归属标记
├── build_result.py        # Diagnostic 与结果
├── local_draft.py         # 本地草稿检查（python -m escaping_site.local_draft）
├── services/github_service.py  # 读 Issue 与仓库归属
├── utils/                 # front matter 解析、HTML sanitizer
└── models/issue_snapshot.py
tests/
```

## 开发流程

涉及行为的非平凡改动遵循：

```text
检查相关代码/调用者/文档
→ 写一个证明用户行为或安全边界的失败测试
→ 最小实现
→ 运行通过
→ 重构
→ 全量验证
→ review diff
```

测试预算、每个行为的测试 owner 和默认不写的测试见[测试策略](docs/agents/testing.md)。
环境准备、局部检查和完整验证统一见[验证命令](docs/agents/testing.md#验证命令)，与
[CI](.github/workflows/ci.yml) 对齐。

## Scratch 材料

- 当期任务材料放 `.scratch/<feature-slug>/`；可重建环境和缓存优先使用系统临时目录。
- 结项保留输入版本、必要反例、结果与未验证范围；旧报告属于其记录的阶段，不代表当前状态。
- `.scratch/` 被 Git 忽略，不等于可随意删除。独有原稿、附件、备份及嵌套仓库须先核对可恢复性；清理按精确路径确认，不整目录删除或自动过期。

## 发布保护

- 未经单独确认不得 push、打 tag、发布到 PyPI，也不得改动任何站点仓库或模板仓库的
  默认分支、Pages 设置或域名。
- `escaping` 与站点不能原子变更；先发布包，再验证一个真实站点，最后同步模板仓库
  （[Deployment](docs/deployment.md#releasing)）。
