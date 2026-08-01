# geoqiao.me 个人站架构建议

> 状态：架构研究与实施建议，不是实现计划。  
> 日期：2026-08-01

## 1. 结论

强烈建议采用 **混合内容架构**：

- GitHub Issues：Blog、Ideas、About 的内容与讨论入口
- `geoqiao/geoqiao.github.io` 仓库文件：站点配置、Home 文案、v1 Projects 清单、主题锁文件、部署工作流；项目详情属于后续阶段
- `geoqiao/escaping`：独立开源的静态站点编译器和 GitHub Action
- 独立主题仓库：仅模板、静态资源和声明式 manifest；固定到完整 commit SHA，显式更新
- GitHub Pages Artifact：托管生成物，不再把 HTML commit/push 到部署分支

这比“全部放 Issue”更易于维护结构化项目页面，也比“全部改为仓库 Markdown”更符合保留 GitHub Issues CMS 编辑体验的目标。

## 2. 参考项目与站点所得

### 2.1 参考站点

通过 Paseo 内置 Browser 直接观察：

- [CatCoding Ideas](https://catcoding.me/ideas/)：倒序短记录流，日期主导，条目从一句话到数段文字，不需要完整博文结构。
- [CatCoding Project](https://catcoding.me/project/)：项目按分组展示，卡片包含名称、简介、topics、stars、forks、主语言。
- [geoqiao 当前 Blog](https://geoqiao.github.io/blog/)：分页文章归档，标题、日期与标签清晰，现有内容迁移价值较高。
- [DrPika 首页](https://www.drpika.com/)：欢迎 Hero 是视觉主体，主要入口简洁；适合借鉴信息层级，而不是复制视觉。
- [geoqiao Atom](https://geoqiao.github.io/atom.xml)：已有全内容 Atom feed，可继续沿用语义。

### 2.2 成熟社区实现

- [Gmeek](https://github.com/Meekdai/Gmeek)：Issue 作为 CMS，Actions 编译静态站；labels、single page、URL 模式各司其职。
- [imfing/issues-blog](https://github.com/imfing/issues-blog)：Issue 转换为 Hugo 内容，再静态构建。
- [mrcaidev/github-issue-as-a-cms](https://github.com/mrcaidev/github-issue-as-a-cms)：先将 GitHub 数据转换为稳定 `Post` 模型，再交给 Astro 页面层。
- [Hugo content types](https://gohugo.io/content-management/types/)、[Jekyll collections](https://jekyllrb.com/docs/collections/)、[Astro content collections](https://docs.astro.build/en/guides/content-collections/) 都采用“先建内容模型，再生成路由”的方式，而不是让远端 API 对象直接泄漏到模板。

共同规律是：**CMS、内容模型、渲染、部署是四个不同边界**。

## 3. 三种架构比较

| 方案 | 编辑体验 | 结构化内容 | URL/SEO 可控性 | 测试性 | 长期复杂度 |
|---|---|---:|---:|---:|---:|
| 全部 Issues | Blog 很好；Projects 别扭 | 低 | 中 | 中低 | 高，需不断发明 label/front matter 协议 |
| **Issues + repo content** | **Blog/Ideas/About 好；Projects 也好** | **高** | **高** | **高** | **中，职责最清楚** |
| 全部 repo Markdown + Issue comments | 本地写作好；移动端编辑差 | 高 | 高 | 最高 | 中，但违背保留 Issues CMS 的目标 |

推荐第二种。

SEO 最终取决于输出 HTML、canonical、站内链接和 sitemap，而不是源内容存放在 Issue 还是 Markdown。混合架构不会天然损害 SEO。

## 4. 仓库职责

```text
geoqiao/geoqiao.github.io             # 个人站控制面
├── Issues                            # Blog / Ideas / About
├── site.yaml                         # 品牌、导航、域名、内容选择规则
├── data/projects.yaml                # v1 项目目录、排序、featured、fallback 元数据
├── overrides/                        # 一层站点模板/静态资源覆盖
├── theme.lock                        # 主题 repo + immutable commit SHA
├── scripts/issue-upload              # Local Draft → 未发布 Issue 的薄适配器
└── .github/workflows/pages.yml       # build + validate + Artifact deploy

geoqiao/escaping                      # 通用开源引擎
├── CLI / Action
├── GitHub Issue adapter
├── content compiler / route registry
├── renderer / validators
└── 不包含个人站配置、PAT 部署逻辑和官方主题资源

geoqiao/escaping-theme-geoqiao        # 独立声明式主题
├── theme.yaml                        # theme_api_version / capabilities
├── templates/
└── static/
```

生成的 HTML 不进入 `geoqiao.github.io` 的 Git 历史，只作为 Pages Artifact 部署。

## 5. 页面与数据源

| 页面 | 数据源 | 生成方式 |
|---|---|---|
| `/` | `site.yaml` + 聚合结果 | 欢迎 Hero + 最近 5 篇 Blog；可附精选项目入口 |
| `/blog/` | `type:blog` Issues | 全量归档、分页 |
| Blog detail | 单个 Blog Issue | 标题/正文/时间/标签/评论 |
| `/tags/` | 已发布 Blog 派生 | 只统计 `tag:*` labels |
| `/tags/{slug}/` | 已发布 Blog 派生 | 标签归档 |
| `/projects/` | `projects.yaml` + GitHub API enrichment | v1 仅生成策展项目卡片并链接 GitHub，不生成详情页 |
| `/ideas/` | `type:idea` Issues | 倒序短记录流 |
| `/ideas/{number}/` | 单个 Idea Issue | 自动详情/永久链接；可链接到 Issue 评论 |
| `/about/` | 配置指定的唯一 Issue | 正文来自 Issue，评论绑定同一 issue number |
| `/atom.xml` | 已发布 Blog | v1 保持 Blog-only；Ideas feed 后续独立增加 |

### 5.1 Home

Home 是品牌入口，不应被建模成普通 Issue：

- Hero 约占首屏主体，包含姓名、定位、简短介绍和主要入口
- 下方显示最近 5 篇 Blog
- 可再显示 2–3 个 featured Projects，但不应挤压欢迎区域
- 文案和 CTA 属于站点配置或 `home.md`，而不是时间流内容

### 5.2 Blog

每篇 Blog 对应一个 Issue。GitHub 原生字段承担：

- Issue title：文章标题
- Issue body：正文
- Issue number：不可变内容 ID
- labels：内容类型、发布状态、tags
- author / created_at / updated_at：作者与时间

YAML front matter 只保存 GitHub 原生字段无法可靠表达的页面元数据：

```yaml
---
slug: rust-in-cloudflare-incident
description: Cloudflare 事故中的 Rust 相关技术分析
created_date: "2026-07-20"
---
```

新 Blog 的 canonical route 固定为 `/blog/{slug}/`。`slug` 和 `description` 是发布必填项，`slug` 首次发布后冻结。`created_date` 记录内容真实创建日期；GitHub Issue 原生 `created_at` 作为发布时间。

### 5.3 Ideas

推荐“一条 Idea 一个 Issue”，不要把所有想法写进一个滚动 Issue，也不要把作者短记录写成 comments：

- Issue title 是简短摘要，body 是必填的 Idea 正文
- `/ideas/` 聚合展示，视觉接近 CatCoding
- Issue number 自动提供稳定锚点/详情 URL
- `created_date` 在 Idea 列表与详情展示；排序仍使用 Issue 原生 `created_at`
- Idea 可使用 `tag:*` labels 并在自身页面展示，但不进入 Blog `/tags/` taxonomy
- 读者评论仍属于对应 Issue，不与其他 Idea 混合

### 5.4 About

About 是 singleton。站点配置中的 Site Profile 只保留全站复用的 `avatar`、一句话 `short_bio` 和 `links`；完整介绍与 expertise 属于 About Issue Markdown，避免两个权威正文来源：

```yaml
about:
  issue_number: 123
```

不要只靠 `type:about` 查询后假设结果恰好只有一个。构建时验证：

- Issue 作者在 allowlist
- 有 `published` label
- 必须有且仅有 `type:about`
- route 固定为 `/about/`，Issue 标题变更不影响 URL
- 页面可组合 Site Profile 的头像/链接与 Issue 正文，但不展示 `created_date`
- Utterances 使用该 Issue number，评论无需触发重新构建

### 5.5 Projects

采用分级模型，但 **v1 只实施第一级**：

1. **v1 目录项目**：只在 `data/projects.yaml` 登记，生成卡片并链接 GitHub。
2. **后续成熟项目**：按真实需求增加 repo Markdown 详情页。
3. **后续独立文档站**：项目足够成熟时链接到独立 docs 域名；个人站保留摘要卡片。

示例：

```yaml
projects:
  - slug: escaping
    title: Escaping
    repository: geoqiao/escaping
    summary: A static personal-site generator powered by GitHub Issues.
    featured: true
    order: 10
```

GitHub API 可补充 stars、forks、language、topics，但这些只是展示增强：API 临时失败时应使用 manifest fallback 或省略动态数字，不应阻断整站构建。

重点项目的标准区块和专属页面属于后续阶段，不进入 v1。未来实现时仍通过共享设计系统和站点 `overrides/` 完成，不把可执行插件放入主题。

## 6. Issue 发布契约

正式规范见 [`docs/contracts/issue-content-v1.md`](../docs/contracts/issue-content-v1.md)。

使用已确认的 **`published` + 作者 allowlist**：

- 类型 labels：`type:blog`、`type:idea`、`type:about`
- 发布 label：`published`
- 展示标签：`tag:python`、`tag:life`
- 作者：`content.allowed_authors: [geoqiao]`
- API 查询显式使用 `state=all`；close Issue 不应意外删除已发布内容
- 排除 Pull Requests
- 每个 Issue 必须恰好有一个 `type:*` label
- `published`、`type:*` 等控制标签永不进入 Tags 页面

只有同时满足以下条件才进入站点：

```text
author in allowlist
AND label contains published
AND exactly one supported type label
AND item is not a Pull Request
```

## 7. 本地 Markdown → Issue 工作流

v1 采用一次性、单向上传，不构建同步系统，也不跟踪 Local Draft 状态。

### 7.1 推荐体验

```bash
# Issue Draft Uploader 校验 Local Draft，并创建未发布 Issue
./scripts/issue-upload drafts/rust-cloudflare.md
```

上传器将 Local Draft 转换成 Issue title、`type:*` / `tag:*` labels 和符合当前唯一格式的 Issue body，然后调用官方 GitHub CLI：

```bash
gh issue create --repo geoqiao/geoqiao.github.io \
  --title "..." \
  --body-file post.md \
  --label "type:blog,tag:rust"
```

创建请求不包含 `published`。命令成功后只输出 Issue number 和 URL；后续内容编辑与发布完全在 GitHub 中完成。用户添加 `published` label 后内容进入站点；Site Compiler 始终使用 Issue 原生 `created_at` 作为发布时间。

参考：[GitHub CLI `gh issue create`](https://cli.github.com/manual/gh_issue_create)。本地只需执行一次 `gh auth login`，不把 Token 写进文章或仓库。

### 7.2 Authority

- Local Draft 只是创建 Issue Content 的一次性输入。
- Issue 创建成功后，GitHub Issue 是唯一权威来源。
- 上传器不回写 `issue_number`，不生成 sidecar，不保存远端 hash 或时间戳。
- 上传器不更新、拉取、合并或同步既有 Issue。
- 本地文件在上传成功后没有生命周期或同步作用，可以由用户自行保留或删除。

Site Compiler 仍以 GitHub 原生 title/labels 为准，并从 Issue body front matter 读取 `slug`、`description` 和 `created_date`。为了保持 `escaping` 核心“只负责构建”的边界，Issue Draft Uploader 独立于 Site Compiler；`escaping init` 最多复制脚手架，不拥有上传行为、认证或 Issue mutation。

## 8. 引擎内部边界

当前模板直接消费 `PyGithub.Issue`，使 GitHub API 结构、内容规则和页面结构耦合。已接受的最小演进为：

```text
PyGithub Issue ─> GitHubIssueSource ─> IssueSnapshot[] ─┐
                                                        ├─> SiteModelBuilder ─> SiteModel + RouteRegistry
projects.yaml ────────> ProjectCatalogSource ─> Project[]┘                         │
                                                                                    └─> SiteRenderer ─> RSS / sitemap / canonical / HTML
```

`IssueSnapshot` 只是一次构建期间隔离 PyGithub 的内存数据，不是同步状态、缓存或第二内容来源。`SiteModelBuilder` 集中完成 published/author/type 选择、front matter 解析、字段验证、内容类型转换、tags 聚合和 route collision 检查。

核心 domain DTO：

- `IssueSnapshot`
- `BlogPost`
- `Idea`
- `AboutPage`
- `Project`
- `Tag`
- `Route`
- `SiteModel`

模板只接收 DTO，不接收 PyGithub 对象，也不解释 YAML 或 labels。`RouteRegistry` 是 sitemap、canonical、RSS、站内链接和输出路径的唯一来源，避免 Python 与 Jinja 各自硬编码 `/blog/`、`/tags/`。

这已经足够，不需要通用 CMS registry、运行时插件框架、数据库或增量缓存系统。

## 9. 主题安装与更新体验

采用“独立 Git 仓库 + 锁定 commit + 本地缓存”：

```yaml
# theme.lock
theme:
  repository: https://github.com/geoqiao/escaping-theme-geoqiao.git
  commit: 0123456789abcdef0123456789abcdef01234567
  api_version: 1
```

行为：

- `escaping build`：缓存中已有该 commit 就直接使用，不联网更新
- 首次缺失：浅 fetch 指定 commit 到本地 cache
- CI runner：每次环境是临时的，可借助 Actions cache；即使重新 fetch 也始终是同一 commit
- `escaping theme update <version>`：用户显式执行，更新 lockfile；构建永不自动升级
- 模板查找顺序：`site overrides` → `locked theme`
- `theme.yaml` 声明 API version、必需模板、资源目录与能力
- v1 主题只允许 Jinja 模板、CSS、JS、图片和声明式 manifest，不加载任意 Python 扩展

因此用户通常只在首次安装或主动升级时感知主题下载，不需要每次手工拉仓库。

## 10. GitHub Pages Artifact 工作流

工作流应位于 `geoqiao.github.io`，因为 Pages Artifact 部署到 workflow 所属仓库：

```text
Issue edited/labeled or site repo pushed
  → checkout site repo
  → install pinned escaping
  → resolve pinned theme
  → fetch Issues + read local Projects
  → compile SiteModel
  → render to _site
  → tests / link / XML / canonical validation
  → upload-pages-artifact
  → deploy-pages
```

官方流程：

- [`actions/upload-pages-artifact`](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [`actions/deploy-pages`](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- Settings → Pages → Source 选择 **GitHub Actions**

最小权限：

```yaml
permissions:
  contents: read
  issues: read
  pages: write
  id-token: write
```

触发事件：

- `push` 到站点仓库 main，限制到配置/content/theme lock/workflow 路径
- `issues`: opened、edited、labeled、unlabeled、closed、reopened
- `workflow_dispatch`

不监听 `issue_comment`：Utterances 实时读取评论，评论变化不改变静态 HTML。

同仓库部署不需要个人 PAT。Actions 自动签发的短期 `GITHUB_TOKEN` 读取 Issue；`deploy-pages` 使用 `pages:write` 和 OIDC `id-token:write` 完成 Pages 部署。

## 11. geoqiao.me 与 SEO

### 11.1 原则

- 全站只声明 `https://geoqiao.me` 为 canonical origin
- sitemap、Atom、Open Graph、Twitter Card、JSON-LD 使用同一 URL builder
- Home/About 添加 `Person` / `WebSite`；Blog detail 添加 `BlogPosting`；Project 可按实际性质使用 `SoftwareSourceCode`
- Atom 增加 `rel="self"`，feed `updated` 使用最新文章更新时间，而不是每次构建时间
- 主 RSS v1 只包含 Blog，避免突然改变已有订阅语义

Google 官方 canonical 指南：[Canonicalization](https://developers.google.com/search/docs/crawling-indexing/canonicalization)。

### 11.2 URL 迁移决定

Blog canonical route 统一切换为 `/blog/{slug}/`。历史 `.html` URL 直接放弃，不生成 alias 或 compatibility redirect；该决定明确接受旧链接失效和潜在 SEO 损失，以换取单一 URL 模型。自定义域名切换时仍需验证 HTTPS、canonical、sitemap 和旧 host 行为。

## 12. 安全与检验门禁

现有高行覆盖率不能替代产物验证。实施时应 TDD 覆盖：

1. YAML front matter 安全解析、字段与大小边界
2. `published`、作者 allowlist、type label、PR 排除
3. slug/tag slug 冲突及路径穿越
4. 确认产物不再生成历史 `.html` Blog URL
5. 空 Blog、空 Ideas、空 Projects
6. GitHub API fixture → domain DTO
7. Theme manifest/context contract，Jinja `StrictUndefined`
8. sitemap/Atom XML 解析和语义
9. 全站内部链接与静态资源存在性
10. canonical、OG、RSS URL 一致性
11. Markdown sanitizer：阻断 script、事件属性和危险 URL scheme
12. 安全输出目录 + 临时目录构建 + 成功后替换
13. Ruff、format、ty、pytest 通过后才允许 deploy
14. Paseo Browser 做 Home/Blog/Ideas/Projects/About 的桌面与移动 smoke/a11y 检查

## 13. 分阶段实施

### Phase 0：冻结现状

- 导出现有 Issue、标签、文章 URL、评论映射
- 增加安全路径、tag slug、空博客等回归测试
- 建立 CI gate
- 暂不切域名、主题或部署方式

### Phase 1：引擎解耦但保持等价输出

- 引入 DTO、Issue adapter、RouteRegistry
- 模板不再依赖 PyGithub Issue
- 支持外部 theme path、manifest、lock/cache 和 site override
- Escape1 与 Escape2 同步迁移到 SiteModel interface，并继续兼容一个版本周期

### Phase 2：站点仓库与 Artifact 部署

- 将 `geoqiao.github.io` 变成源码/control repo
- workflow 移至该仓库
- 使用官方 Pages Artifact，不再 PAT clone/push
- 并行生成 `_site-v2` 验证后才切换部署

### Phase 3：多内容类型

- 增加 `published`、`type:*`、`tag:*` 与作者 allowlist
- 新增 About Issue、Ideas、目标 Home
- RSS 保持 Blog-only
- 切换严格解析前，手工将历史 Blog Issues 全部补齐 label/front matter
- 在测试环境完成全站生成后一次性切换，不保留旧 parser、fallback 或兼容开关

### Phase 4：Projects v1 与自定义域名

- 上线只包含 GitHub 链接的普通项目 catalog，不生成项目详情页
- 完整 sitemap/canonical/OG/JSON-LD
- 配置 `geoqiao.me` 和 HTTPS
- 观察放弃历史 `.html` URL 后的索引变化与 404 情况

### Phase 5：按真实需求增强

- 独立 Ideas feed
- 成熟项目 Markdown 详情页或独立 docs
- 项目专属区块
- 可选从站点脚本提炼通用 Issue authoring 命令

## 14. 明确不做

- 不引入数据库、SSR、Serverless Function、自建 CMS 后台
- 不把 Blog/About 迁成 repo Markdown
- 不把 Projects 强行做成 Issues
- 不自动展示全部 GitHub 仓库
- 不在 v1 做双向 Markdown↔Issue 同步
- 不在 v1 做增量构建状态机
- 不做可执行 Python 主题插件
- 不自动升级 escaping 或主题
- 不因评论变更重建

## 15. 当前代码的关键演进点

- `src/github_blog/cli.py`：目前一个 `BlogGenerator` 同时负责获取、分类、路由、渲染和写盘，需要逐步变成 SiteCompiler 编排。
- `src/github_blog/services/github_service.py`：目前按 token 用户隐式筛选；需改为显式 author/type/published 策略并读取 all states。
- `src/github_blog/services/render_service.py`：目前模板直接接收 `Issue`；需改接 DTO，并集中 route/meta context。
- `src/github_blog/config.py`：需让配置严格、可执行，拒绝未知字段和危险路径。
- `templates/seo/sitemap.xml.j2`：应由 RouteRegistry 提供页面集合，不再只认识 Blog/Tag。
- `.github/workflows/gen_site.yml`：当前 PAT clone/push 应由站点仓库内的 Pages Artifact workflow 替代。

这条路线可以保留当前内容和写作习惯，又能逐步扩展成真正的个人品牌站，而不是把现有博客生成器一次性推倒重写。
