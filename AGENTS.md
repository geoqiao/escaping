# AGENTS.md

本文件是 `escaping` 仓库的 coding-agent 指南。以当前代码、测试和 domain docs 为准。

## 产品与边界

`escaping` 是基于 GitHub Issues 的 opinionated personal-site generator。它生成 Home、
Blog、Ideas、About、Projects、Tags、Atom、sitemap 和 robots。

仓库职责：

- 生成器拥有 compiler、models、validators、`config.example.yaml` 和内置 Themes；
- 站点仓库拥有真实 `config.yaml`、Pages workflow、`CNAME` 和可选本地 Theme；
- Site Orchestrator pin 生成器 release/完整 SHA；生产 workflow 使用短期
  `GITHUB_TOKEN`，不得硬编码 PAT。

P3 产品决策未重新开启前，保留 Ideas 和 Projects，不引入 plugin system。

## Domain 与任务文档

- Ubiquitous language：`CONTEXT.md`
- ADR：`docs/adr/`
- Issue Content：`docs/contracts/issue-content-v1.md`
- 测试策略：`docs/agents/testing.md`
- Local Markdown tickets：`.scratch/<feature-slug>/`
- Deployment contract：`docs/deployment.md`

## 关键实现约束

1. `Settings` 显式注入 compilation 和 `SiteBuilder`；禁止全局配置单例。
2. Renderer 和 artifact validator 只读取 `SiteModel`；Theme 作为已加载依赖注入。
3. `RouteRegistry` 构造唯一的 `Route`；页面直接持有完整 Route，不手工拼接输出路径。
4. Config-relative Theme/output 路径以 Config 文件目录为根，不能依赖 process CWD。
5. `ThemeLoader` 只加载 package resources 或本地目录；不得加入 Git/HTTP
   fetch、cache、update 或 `theme_lock`。
6. `geoqiao.me` 是默认内置 Theme；Escape1/Escape2 是内置替代 Themes。
7. Theme 静态 URL 使用以 `/` 开头的 `{{ theme_path }}`。
8. Utterances 行为位于共享 `src/escaping/static/comments.js`。必须保留：
   - immutable Issue number binding；
   - `postMessage` + `MutationObserver` 自动主题同步；
   - message origin/source 校验；
   - Safari 注入 iframe `loading="lazy"` 移除兼容。
9. 不得弱化 HTML sanitizer、output containment、artifact validator 或 atomic output
   staging。
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
├── themes/{geoqiao.me,Escape1,Escape2}/
├── models/
└── services/
config.example.yaml
tests/
```

生成器仓库不应重新加入真实生产 `config.yaml` 或生产 Pages workflow。

## 开发流程

非平凡改动遵循：

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

## 常用命令

```bash
uv sync
uv run pytest -q
uv run ruff check src/escaping tests
uv run ruff format --check src/escaping tests
uv run ty check
git diff --check
```

本地生成：

```bash
export GITHUB_TOKEN=...
uv run escpe --config /absolute/or/relative/site/config.yaml
uv run python -m http.server 8000 --directory /path/to/site/output
```

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

修改 Theme 后运行：

```bash
uv run pytest -q tests/test_template_integrity.py tests/test_package_consumer.py
```

Theme contract 必须同时覆盖模板渲染、keyboard navigation、本地 overflow、comments
container/script 和 package assets。

## 部署保护

- `geoqiao.github.io` 的发布源是 GitHub Pages artifact，不是 `main` 根目录。
- 跨仓库迁移分支可以 push；未经单独确认不得 merge `main`、运行生产 deploy 或改变
  Pages 设置。
- workflow 必须 pin 完整 generator SHA/release，显式传入站点 Config，并上传站点仓库
  Config-relative `output/`。
- 生成器与站点不能原子变更；先验证兼容 consumer，再更新站点 pin，最后部署。
