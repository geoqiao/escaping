# AGENTS.md

本文件是 `escaping` 仓库的 coding-agent 指南。以当前代码、测试和 domain docs 为准。
架构与完整文档导航见[维护者入口](docs/dual-repo-architecture.md)。

## 产品与边界

`escaping` 是基于 GitHub Issues 的 opinionated personal-site generator。它生成 Home、
Blog、Ideas、About、Projects、Tags、Atom、sitemap 和 robots。

仓库职责：

- 生成器拥有 compiler、models、validators、`config.example.yaml` 和内置 Themes；
- 站点仓库拥有真实 `config.yaml`、Pages workflow、`CNAME` 和可选本地 Theme；
- Site Orchestrator pin 生成器 release/完整 SHA；生产 workflow 使用短期
  `GITHUB_TOKEN`，不得硬编码 PAT。

保留 Ideas 和 Projects，不引入 plugin system；改变这些产品边界需单独确认。

## 按任务读取

探索代码前先读 [CONTEXT.md](CONTEXT.md) 和相关 [ADR](docs/adr/)，其余按需读取。

| 任务 | 文档 |
| --- | --- |
| 内容与发布规则 | [Issue Content v1](docs/contracts/issue-content-v1.md) |
| 可选草稿创作辅助 | [Local Draft v1](docs/contracts/local-draft-v1.md)，不用于同步或发布 |
| 开发与验证 | [测试策略](docs/agents/testing.md) |
| 版本、安装与部署 | [Deployment contract](docs/deployment.md) |
| Issues 与 specs | [GitHub tracker](docs/agents/issue-tracker.md)、[triage 标签约定](docs/agents/triage-labels.md)；使用前检查标签是否存在 |
| Domain 文档维护 | [single-context 约定](docs/agents/domain.md) |

## 关键实现约束

1. `Settings` 显式注入 compilation 和 `SiteBuilder`；禁止全局配置单例。
2. Renderer 和 artifact validator 只读取 `SiteModel`；Theme 作为已加载依赖注入。
3. `RouteRegistry` 构造唯一的 `Route`；页面直接持有完整 Route，不手工拼接输出路径。
4. Config-relative Theme/output 路径以 Config 文件目录为根，不能依赖 process CWD。
5. `ThemeLoader` 只加载 package resources 或本地目录；不得加入 Git/HTTP
   fetch、cache、update 或 `theme_lock`。
6. Quiet 是唯一内置及默认 Theme；保留本地 Theme API 2。已移除的内置名称必须明确失败，不得静默回退。
7. Theme 静态 URL 使用以 `/` 开头的 `{{ theme_path }}`。
8. Utterances 行为位于共享 `src/escaping/static/comments.js`。必须保留：
   - immutable Issue number binding；
   - `postMessage` + `MutationObserver` 自动主题同步；
   - message origin/source 校验；
   - Safari 注入 iframe `loading="lazy"` 移除兼容。
9. 不得弱化 HTML sanitizer、output containment、artifact validator 或 staged output
   publication。
10. GitHub Token 环境变量名由 `settings.security.token_env` 决定。

## 当前结构

```text
src/escaping/
├── content_compiler.py
├── site_builder.py
├── routes.py
├── site_compiler.py
├── artifact_validation.py
├── output_staging.py
├── theme.py
├── static/comments.js
├── themes/Quiet/
├── models/
└── services/
config.example.yaml
tests/
```

生成器仓库不应重新加入真实生产 `config.yaml` 或生产 Pages workflow。

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

测试原则：

- 每个 Ticket 默认 3–6 个高信号逻辑测试；
- 一个行为只有一个主要 owner；上层只保留真实 tracer；
- 多 Theme 使用参数化 contract，禁止复制测试矩阵；
- 不测试 private helper、mock 调用形状或 getter；
- 优先完整静态站点、真实链接、wheel consumer 和浏览器行为；
- 重构测试本身无需先制造失败，但必须先记录通过基线。
- 纯文档改动验证链接、路径和示例，不为制造红灯添加行为无关的测试。

## 验证与本地构建

环境准备、局部检查和完整验证统一见[验证命令](docs/agents/testing.md#验证命令)，与
[CI](.github/workflows/ci.yml) 对齐；不要遗漏 `starter/.github/scripts`。
本地生成见[本地构建步骤](docs/site-inputs.md#local-build)。
`output/` 必须作为 HTTP document root；不要使用 `/output/` URL 前缀。

## Config 与安全

- Pydantic models 使用 `extra="forbid"`；未知字段应失败。
- URL link 只允许 HTTPS、`mailto:`、root-relative 或 fragment；资源 URL 只允许
  HTTPS/root-relative。
- repository 使用 `owner/repo` 格式。
- Jinja 使用 autoescape + `StrictUndefined`。
- Markdown body 进入模板前必须经过 sanitizer。
- 禁止通过删除校验或错误处理来简化代码。

## Themes

内置 Theme 位于 `src/escaping/themes/<name>/`，每个 Theme 包含 `theme.yaml`、页面
模板和 `static/`。共享评论逻辑不复制进 Theme source；构建时复制到所选 Theme 的
输出 asset directory。

修改 Theme 后运行[局部验证中的 Theme 检查](docs/agents/testing.md#局部验证)。
Theme contract 必须同时覆盖模板渲染、keyboard navigation、本地 overflow、comments
container/script 和 package assets。

## Scratch 材料

- 当期任务材料放 `.scratch/<feature-slug>/`；可重建环境和缓存优先使用系统临时目录。
- 结项保留输入版本、必要反例、结果与未验证范围；旧报告属于其记录的阶段，不代表当前状态。
- `.scratch/` 被 Git 忽略，不等于可随意删除。独有原稿、附件、备份及嵌套仓库须先核对可恢复性；清理按精确路径确认，不整目录删除或自动过期。

## 部署保护

- `geoqiao.github.io` 的发布源是 GitHub Pages artifact，不是 `main` 根目录。
- 跨仓库迁移分支可以 push；未经单独确认不得 merge `main`、运行生产 deploy 或改变
  Pages 设置。
- workflow 必须 pin 完整 generator SHA/release，显式传入站点 Config，并上传站点仓库
  Config-relative `output/`。
- 生成器与站点不能原子变更；先验证兼容 consumer，再更新站点 pin，最后部署。
