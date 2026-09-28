# AGENTS.md

本文件是 `escaping` 仓库的 coding-agent 指南。以当前代码、测试和 domain docs 为准。
架构与完整文档导航见[维护者入口](docs/dual-repo-architecture.md)，主题设计见
[ADR-0008](docs/adr/0008-theme-api-3-data-presentation-split.md)、
[ADR-0009](docs/adr/0009-site-owned-pages-redirects-and-sub-paths.md) 和
[ADR-0010](docs/adr/0010-themes-from-github-repositories.md)。

## 产品与边界

`escaping` 把 GitHub Issues 变成个人网站：Home、Blog、Ideas、About、Projects、Tags、
Atom、sitemap、robots、搜索索引和旧地址跳转页。

核心分工：**生成器只管数据，主题只管呈现。**

- 生成器负责：读取 Issue、净化 HTML、分配唯一网址、生成 Atom/sitemap/搜索索引、
  检查站内链接和资源、安全地替换输出目录。
- 主题负责：页面长什么样、放哪些 SEO 标签、界面文字、主题自己的选项；只需
  `blog.html` 和 `post.html`，其余页面按固定规则退回这两个模板。
- 站点仓库负责：真实 `config.yaml`（包括有哪些页面、地址、额外页面和旧地址跳转）、
  可选的本地主题、Pages workflow 和 `CNAME`。

仓库职责：

- 生成器拥有 compiler、models、`config.example.yaml`、内置主题 Quiet 和可复用
  Action（`action.yml`）；
- 站点仓库 pin 生成器的 release tag 或完整 SHA；生产 workflow 使用短期
  `GITHUB_TOKEN`，不得硬编码 PAT。

Issue 是唯一内容来源，`published` 标签控制发布，内容类型只有 Blog、Idea、About。
主题只能是模板、静态文件和 `theme.yaml`，不执行主题提供的 Python 代码。改变这些
边界需单独确认。

## 按任务读取

探索代码前先读 [CONTEXT.md](CONTEXT.md) 和相关 [ADR](docs/adr/)，其余按需读取。

| 任务 | 文档 |
| --- | --- |
| 内容与发布规则 | [Issue Content v1](docs/contracts/issue-content-v1.md) |
| 主题与主题选项 | [主题编写指南](docs/themes/authoring.md)、[Quiet](docs/themes/quiet.md) |
| Config 字段 | [Site inputs](docs/site-inputs.md) |
| 可选草稿创作辅助 | [Local Draft v1](docs/contracts/local-draft-v1.md)，不用于同步或发布 |
| 开发与验证 | [测试策略](docs/agents/testing.md) |
| 版本、Action 与部署 | [Deployment contract](docs/deployment.md) |
| Issues 与 specs | [GitHub tracker](docs/agents/issue-tracker.md)、[triage 标签约定](docs/agents/triage-labels.md)；使用前检查标签是否存在 |
| Domain 文档维护 | [single-context 约定](docs/agents/domain.md) |

## 关键实现约束

1. **Config 分两层。** 判断一个值放哪层，只问一句：换了主题之后它还有意义吗？
   有意义放站点层（`github`、`site`（含 `navigation`）、`profile`、`about`、`paths`、
   `pages`、`redirects`、`projects`、`comments`、`seo`、`security`）；没意义放主题层（`theme.options`），由主题的
   `theme.yaml` 声明类型和默认值。生成器代码里不得出现只为某个主题服务的字段。
2. **Quiet 没有特权。** Quiet 是唯一内置和默认主题，但与本地主题走同一套加载、
   选项、页面和字符串机制；编译器不得按主题名分支。
3. **模板只拿到四个变量**：`site`、`page`、`theme`（选项最终值）、`t`（界面文字）。
   新数据加进这四个对象，不新增顶层变量。
4. `Settings` 显式注入；禁止全局配置单例。Renderer 与 artifact validator 只读
   `SiteModel` 和已加载的主题。
5. `RouteRegistry` 是唯一构造 `Route` 的地方，包括 `pages.extra` 的页面，也负责给
   子路径站点加前缀。页面持有完整 Route，不手工拼接地址或输出路径；主题自己的
   地址用 `url` 过滤器。
6. Config 中的相对路径（主题、输出目录）以 Config 文件所在目录为根，不依赖 CWD。
7. 主题来自三处：内置、站点仓库里的目录、`github.com/…@版本`。GitHub 主题由
   `remote_theme.py` 每次构建下载到临时目录，用完删除，不缓存；`ThemeLoader`
   本身只读目录，不联网、不执行主题代码、拒绝符号链接。`extends` 可指向内置主题
   或 GitHub 地址。模板在 Jinja 沙箱里运行（构建进程持有 token），不得为主题放宽。
8. 主题静态文件发布在 `/assets/`，生成器共享脚本（评论、Mermaid）在
   `/assets/escaping/`；主题不得占用 `static/escaping/`。
9. Utterances 行为位于共享 `src/escaping/static/comments.js`。必须保留：
   - immutable Issue number binding；
   - `postMessage` + `MutationObserver` 自动主题同步；
   - message origin/source 校验；
   - Safari 注入 iframe `loading="lazy"` 移除兼容。
10. **构建前先检查本地输入。** Config、主题加载、全部模板编译、输出目录安全在访问
    GitHub 之前完成；这些错误让构建直接失败，不产生半成品。
11. **错误按范围处理。** 单个 Blog/Idea Issue 的内容错误只跳过该 Issue，报告 Issue
    编号，照常发布其余内容，CLI 以状态码 2 结束。Config、主题、About 选择、站点级
    路由冲突属于整站错误，不发布。
12. 构建时检查只管完整性：每个路由都有文件、站内链接和资源不断、输出不越界。
    SEO 标签是否规范由主题自己的测试和 `escpe theme check` 负责，不在每次构建拦截。
13. 不得弱化 HTML sanitizer、output containment、输出目录归属检查或 staged output
    publication；输出目录里不是本工具生成的文件时拒绝覆盖。
14. GitHub Token 环境变量名由 `security.token_env` 决定。

## 当前结构

```text
src/escaping/              # 按构建顺序
├── cli.py                 # escpe build / escpe theme check
├── site_compiler.py       # 预检 → 拉取 → 编译 → 渲染 → 校验 → 发布
├── config.py              # 站点层 Config
├── site_inputs.py         # 从仓库和 GitHub 资料补全缺省的 Config 值
├── theme.py               # theme.yaml API 4、extends、模板回退、选项校验、字符串
├── remote_theme.py        # github.com/… 主题：下载、只解压指定目录
├── output_safety.py       # 输出目录不越界、归属标记
├── services/              # github_service.py 读 Issue；render_service.py 渲染
├── content_compiler.py    # Issue → Blog/Idea/About，坏 Issue 跳过
├── content_validation.py  # Issue 与本地草稿共用的内容规则、Markdown 渲染
├── projects.py            # config 里的 Projects
├── site_builder.py        # SiteModel：固定页面、额外页面、导航、跳转页
├── routes.py              # RouteRegistry
├── blog_archive.py、tag_taxonomy.py、atom_feed.py、search.py
├── artifact_validation.py # 替换线上产物前的完整性检查
├── output_staging.py      # 先写临时目录，成功后替换
├── build_result.py        # Diagnostic 与退出码
├── local_draft.py         # 本地草稿检查（python -m escaping.local_draft）
├── utils/                 # front matter 解析、HTML sanitizer
├── models/
├── static/                # comments.js、mermaid.js、mermaid/（发布到 /assets/escaping/）
└── themes/quiet/
action.yml                 # 站点仓库使用的可复用 Action
config.example.yaml
starter/                   # escaping-template 仓库的内容来源
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
- 多个主题使用参数化 contract（Quiet、继承 Quiet 的主题、独立 fixture 主题）；
- 不测试 private helper、mock 调用形状或 getter；
- 优先完整静态站点、真实链接、wheel consumer 和浏览器行为；
- 重构测试本身无需先制造失败，但必须先记录通过基线；
- 纯文档改动验证链接、路径和示例，不为制造红灯添加行为无关的测试。

## 验证与本地构建

环境准备、局部检查和完整验证统一见[验证命令](docs/agents/testing.md#验证命令)，与
[CI](.github/workflows/ci.yml) 对齐。本地生成见[本地构建步骤](docs/site-inputs.md#local-build)。
`output/` 必须作为 HTTP document root；不要使用 `/output/` URL 前缀。

## Config 与安全

- Pydantic models 使用 `extra="forbid"`；未知字段报错并给出最接近的正确写法。
- 错误信息说明位置和原因，不回显字段值（可能含敏感信息）。
- URL link 只允许 HTTPS、`mailto:`、root-relative 或 fragment；资源 URL 只允许
  HTTPS/root-relative。
- repository 使用 `owner/repo` 格式。
- Jinja 使用 `SandboxedEnvironment` + autoescape + `StrictUndefined`。
- Markdown body 进入模板前必须经过 sanitizer。
- 删除防御代码前先确认它防的情况在新结构下确实不会发生；安全边界（第 13 条）不在此列。

## Themes

内置主题位于 `src/escaping/themes/<name>/`，每个主题包含 `theme.yaml`、页面模板和
`static/`。Quiet 拆分为小的 partial 模板，方便站点用 `extends: quiet` 只覆盖一个文件；
重命名或删除 Quiet 的 partial、选项或字符串 key 属于破坏性变更，需写入 CHANGELOG。

修改主题后运行[局部验证中的 Theme 检查](docs/agents/testing.md#局部验证)。
主题 contract 覆盖模板渲染、键盘导航、本地 overflow、评论容器/脚本和包内资源。

## Scratch 材料

- 当期任务材料放 `.scratch/<feature-slug>/`；可重建环境和缓存优先使用系统临时目录。
- 结项保留输入版本、必要反例、结果与未验证范围；旧报告属于其记录的阶段，不代表当前状态。
- `.scratch/` 被 Git 忽略，不等于可随意删除。独有原稿、附件、备份及嵌套仓库须先核对可恢复性；清理按精确路径确认，不整目录删除或自动过期。

## 部署保护

- `geoqiao.github.io` 的发布源是 GitHub Pages artifact，不是 `main` 根目录。
- 跨仓库迁移分支可以 push；未经单独确认不得 merge `main`、运行生产 deploy 或改变
  Pages 设置。
- 站点 workflow 通过 `uses: geoqiao/escaping@<tag 或完整 SHA>` 调用 Action，显式传入
  站点 Config，并上传 Config-relative `output/`。
- 生成器与站点不能原子变更；先验证兼容 consumer，再更新站点 pin，最后部署。
