# 研究：GitHub Issues 作为 CMS 时的 slug 与文章元数据实践

> 目的：判断把 slug 写进 Issue 正文的隐藏 HTML comment 是否属于社区最佳实践，并为 escaping 选择可维护、稳定且低摩擦的方案。
>
> 方法：优先核对成熟 SSG 官方文档，以及 GitHub Issues 博客/CMS 项目的当前源码。源码链接固定到本次检查的 commit，避免 `main` 后续漂移。

## 结论

**隐藏 HTML comment 可以工作，但不能称为社区最佳实践。**

成熟静态站点生成器对“内容自身拥有的扩展元数据”采用的共同模型是 **front matter**；成熟的 Issues CMS 则优先复用 GitHub 原生字段（title、body、labels、author、timestamps、state/pin），对于 GitHub 没有的字段，有项目使用 front matter，也有项目退回 issue number、标题派生 URL 或 slug label。此次检查没有发现所选成熟项目把隐藏 HTML comment 作为 slug 的首选公开契约。

针对 escaping 的约束——继续在 Issues 写作、发布时只手工填写一次英文 slug、之后稳定复用——建议：

1. GitHub 原生字段继续承担其擅长的数据：
   - title → 文章标题
   - body → 正文
   - `published` label → 发布状态
   - 其他 labels → tags
   - author / created_at / updated_at → 作者和时间
2. 仅把 GitHub 没有的一小组字段放在 Issue 正文开头的**显式、可校验 YAML metadata block**：首期只包含 `slug`，未来按真实需求增加 `aliases`、`description`。
3. 由 Issue template 预填 metadata block，用户不需要记忆语法；生成器先解析和校验，再从正文中移除该块。
4. 不把 slug 编进 GitHub label；不在每次构建时重新从标题生成；不依赖在线 AI 翻译。
5. HTML comment 可以作为兼容输入，但不应成为 v1 文档里的 canonical format。

推荐 canonical 写法优先考虑标准 YAML front matter：

```markdown
---
slug: rust-in-cloudflare-incident
---

这里开始写正文。
```

如果认为它在 GitHub Issue 页面中太显眼，可以采用 `github-issue-cms` 已实现的“首个 fenced YAML block”变体；它仍是显式元数据，而不是不可见私有协议：

````markdown
```yaml
slug: rust-in-cloudflare-incident
```

这里开始写正文。
````

## 一、传统 SSG 的共同约定

| 项目 | 官方行为 | 对 escaping 的启示 |
|---|---|---|
| Hugo | `slug` front matter 覆盖 URL 最后一段；`url` 覆盖完整路径；`aliases` 声明旧路径 | slug 与 alias 属于内容元数据，并应持久化而不是每次重算 |
| Jekyll | YAML front matter 必须位于文件开头；单页 `permalink` 可覆盖输出路径 | per-content URL override 放在内容旁边 |
| Hexo | front matter 是文章配置入口；支持 `slug`、`permalink`，CLI 也支持 `--slug` | 手工指定一次 slug 是正式写作流程，不必每次构建生成 |
| Astro | content collection 可由 front matter/data 指定 slug；重复 slug 会报错；schema 校验元数据 | slug 需要 schema、唯一性检查和构建失败反馈 |

一手资料：

- Hugo：[URL management](https://gohugo.io/content-management/urls/) · [Front matter](https://gohugo.io/content-management/front-matter/)
- Jekyll：[Front Matter](https://jekyllrb.com/docs/front-matter/) · [Permalinks](https://jekyllrb.com/docs/permalinks/)
- Hexo：[Front-matter](https://hexo.io/docs/front-matter) · [Permalinks](https://hexo.io/docs/permalinks/) · [Commands (`--slug`)](https://hexo.io/docs/commands)
- Astro：[Content collections](https://docs.astro.build/en/guides/content-collections/) · [Duplicate content entry slug](https://docs.astro.build/en/reference/errors/duplicate-content-entry-slug-error/)

## 二、GitHub Issues 博客/CMS 的真实实现

### 1. Gmeek：GitHub 原生字段 + 标题派生 URL 或 issue number

Gmeek 是本次样本中社区规模最大的纯 Issues 博客项目。它要求 Issue 至少有一个 label；文章 metadata 直接取 Issue title、labels、number、created time、comments 和 pin events。

URL 文件名由全局 `urlMode` 决定：

- 默认 `pinyin`：根据当前标题转拼音；
- `ru_translit`：标题转写；
- `issue`：直接使用不可变 issue number。

它没有把自定义 slug 放在隐藏 HTML comment；默认标题派生模式仍有“改标题导致 URL 变化”的风险，`issue` 模式稳定但不可读。

源码：

- [默认 `urlMode: pinyin`](https://github.com/Meekdai/Gmeek/blob/77a8aaa2b1a5b5d4d5cbb7901ed8fc0559fd5ed4/Gmeek.py#L91)
- [Issue metadata 到 post JSON](https://github.com/Meekdai/Gmeek/blob/77a8aaa2b1a5b5d4d5cbb7901ed8fc0559fd5ed4/Gmeek.py#L314-L355)
- [`createFileName`: issue number / transliteration / pinyin](https://github.com/Meekdai/Gmeek/blob/77a8aaa2b1a5b5d4d5cbb7901ed8fc0559fd5ed4/Gmeek.py#L434-L446)
- [README 写作流程](https://github.com/Meekdai/Gmeek/blob/77a8aaa2b1a5b5d4d5cbb7901ed8fc0559fd5ed4/README.md#L14-L20)

### 2. mrcaidev/github-issue-as-a-cms：issue number 就是 slug

该项目明确把 GitHub Issue 的 number、title、body、comments、state、timestamps、pin 和 labels 映射为博客字段，路由参数 `slug` 实际是整数 issue number，并通过 GraphQL `issue(number:)` 精确读取。

优点是稳定、无需额外元数据；缺点是 URL 不具描述性，不符合本项目已确定的英文可读 URL 目标。

源码：

- [Issue 字段到博客字段的设计表](https://github.com/mrcaidev/github-issue-as-a-cms/blob/076a5cc2a0186d154677711c88459693b662d545/README.md#L15-L46)
- [`slug: number` 与 `issue(number: $slug)`](https://github.com/mrcaidev/github-issue-as-a-cms/blob/076a5cc2a0186d154677711c88459693b662d545/src/utils/post/fetchPostBySlug.ts#L4-L72)

### 3. renatorib/github-blog：支持正文 front matter，但用 slug label 做精确查询

该库会解析 Issue body 开头的标准 YAML front matter，并从输出正文中移除该块。它同时采用 `type:*`、`state:*`、`tag:*`、`flag:*`、`slug:*` labels。

作者详细记录了 slug 取舍：GitHub API 能按 issue number 精确读取，却不能按 title 精确读取；搜索 title 不可靠，因此退回 `slug:my-first-post` label。作者也明确承认该方案“不理想”，因为每篇文章都会创建一个新 label，扩展性差。

这说明：

- Issue body front matter 是已有实践；
- slug label 是为“运行时按 slug 查询单篇 Issue”服务的 API workaround，不适合 escaping 的全量静态构建；escaping 构建时已经拿到全部文章，可在本地检查 slug 唯一性，无需一文一 label。

源码：

- [taxonomy 与 slug label](https://github.com/renatorib/github-blog/blob/4f2a482c69578212bc4f91c44091de69dfc2a99a/README.md#L23-L37)
- [Issue 示例与 front matter 提示](https://github.com/renatorib/github-blog/blob/4f2a482c69578212bc4f91c44091de69dfc2a99a/README.md#L70-L76)
- [作者对 slug label 扩展性问题的说明](https://github.com/renatorib/github-blog/blob/4f2a482c69578212bc4f91c44091de69dfc2a99a/README.md#L239-L301)
- [标准 YAML front matter parser](https://github.com/renatorib/github-blog/blob/4f2a482c69578212bc4f91c44091de69dfc2a99a/src/utils/frontmatter.ts#L1-L17)
- [解析并剥离 front matter](https://github.com/renatorib/github-blog/blob/4f2a482c69578212bc4f91c44091de69dfc2a99a/src/datatypes/Post.ts#L55-L72)

### 4. rokuosan/github-issue-cms：显式支持 Issue body metadata block

这是与 escaping 数据流最直接相似的实现之一：它把 GitHub Issues 转为 Hugo-compatible Markdown，先从正文开头解析 metadata，再从正文中剥离。

当前实现支持三种显式格式：

1. fenced YAML block；
2. `---` 包围的 YAML front matter；
3. `+++` 包围的 TOML front matter。

其测试直接覆盖 metadata 解析和剥离。这是“在 Issues 中保存非原生字段”最强的现成源码证据，但它使用显式 metadata，而不是 HTML comment。

源码：

- [解析顺序与三种 metadata 格式](https://github.com/rokuosan/github-issue-cms/blob/46b8aa3bbc23019ed1c152bc11f76faeaed01950/pkg/core/issue_articles.go#L210-L308)
- [转换 Issue 时解析并剥离 metadata](https://github.com/rokuosan/github-issue-cms/blob/46b8aa3bbc23019ed1c152bc11f76faeaed01950/pkg/core/issue_articles.go#L61-L106)
- [YAML fence / YAML front matter / TOML front matter 测试](https://github.com/rokuosan/github-issue-cms/blob/46b8aa3bbc23019ed1c152bc11f76faeaed01950/pkg/core/issue_articles_test.go#L374-L417)

### 5. imfing/issues-blog：Issue 原生字段生成 Hugo front matter

该项目读取 Issue title、created/updated time 和 labels，生成 Hugo Markdown 的 YAML front matter；正文来自 Issue body，输出文件名仍由标题 sanitize 得到。

它证明了“以 GitHub 原生字段为主、构建边界转换为标准 SSG front matter”的模式，但标题派生文件名仍不能满足编辑标题后 URL 永久稳定的需求。

源码：

- [Issue 字段转 Hugo front matter](https://github.com/imfing/issues-blog/blob/2cbb2b0d8076f16ec431a775a6e82bb14ad3d470/scripts/main.ts#L70-L112)
- [标题 sanitize 后作为文件名](https://github.com/imfing/issues-blog/blob/2cbb2b0d8076f16ec431a775a6e82bb14ad3d470/scripts/main.ts#L128-L134)

## 三、候选方案对比

| 方案 | 社区依据 | 写作体验 | 稳定性/可校验性 | 结论 |
|---|---|---:|---:|---|
| 标准 YAML front matter | Hugo/Jekyll/Hexo/Astro；renatorib；rokuosan | 一次填写，可由模板预填 | 高；成熟 parser/schema | **推荐 canonical** |
| fenced YAML metadata | rokuosan 明确实现 | GitHub 页面更清楚，但可见 | 高；容易剥离和校验 | 可作为 Issues UX 变体 |
| HTML comment | GitHub 官方支持隐藏，但所查项目未把它作为 slug 契约 | 页面最干净 | 自定义 parser；编辑时不明显；容易被误删 | 可兼容，不称最佳实践 |
| `slug:*` label | renatorib | 标签列表严重膨胀 | 可精确 API 查询，但一文一 label | 不适合全量静态构建 |
| issue number | Gmeek / mrcaidev | 零输入 | 最稳定 | 可作 fallback/内部 ID，不满足可读 URL |
| 标题派生 slug | Gmeek / imfing | 零输入 | 改标题即变 URL | 不应作为 canonical |
| 单独 manifest/YAML | 通用数据建模方案 | 写 Issue 后还要改文件 | 高，且不污染正文 | 适合批量治理，不符合一步写作目标 |
| Issue Forms | GitHub 官方；表单结果最终进入 Issue body Markdown | 创建时可校验必填 | 编辑后仍需解析 Markdown；不是独立内容 schema | 可生成写作 UI，不替代 metadata format |

GitHub 官方资料：

- [Issue Forms syntax](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms)
- [Configuring issue templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository)
- [Hiding content with HTML comments](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#hiding-content-with-comments)

## 四、escaping 的建议契约

### Source of truth

- `issue.number`：不可变内部 ID，用于冲突诊断、迁移和评论映射；不必暴露在 canonical URL。
- `slug`：作者显式填写一次，之后视为持久标识；修改必须同时保留旧值到 `aliases`。
- `title`：可自由编辑，不改变 URL。
- `published` + allowed authors：控制是否发布。
- 普通 labels：tags；保留标签不得渲染为 tag。

### 校验

构建必须 fail fast：

- published 文章缺少 slug；
- 重复 slug 或 alias；
- 非小写 ASCII / 非连字符格式；
- 绝对路径、`..`、斜杠、URL query/fragment；
- 与保留路由冲突（例如 `about`、`tags`、`projects`）；
- 超过约定长度；
- 同一正文出现多个 metadata block。

### 迁移

不要一次改掉现有 39 篇文章的公开 URL。先建立旧 URL 清单，再为文章补 slug；新 canonical 上线时为旧路径生成 redirect/alias 页面。提交 sitemap 后再观察索引迁移。

## 五、尚需确认的产品决策

唯一需要用户决定的是：是否接受 GitHub Issue 顶部显示一个很小的 YAML metadata block。

- 接受：采用标准 front matter（最接近跨 SSG 最佳实践）。
- 不接受但仍要求一步写作：采用隐藏 HTML comment，但应诚实标注为 escaping 自定义语法，而非社区标准。
- 不接受任何正文 metadata：改用独立 manifest，承担两步编辑成本。
