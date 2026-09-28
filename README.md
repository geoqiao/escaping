<div align="center">

<img src="docs/assets/escaping-logo.png" alt="escaping logo" width="180">

# escaping

**在 GitHub Issues 写作，拥有自己的个人网站。**

Blog、Ideas、Projects、About、Tags 和 RSS，无需另建一套内容管理系统。

[![Python 3.14.x](https://img.shields.io/badge/Python-3.14.x-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![GitHub Issues](https://img.shields.io/badge/Content-GitHub_Issues-181717?logo=github)](https://docs.github.com/issues)
[![Static Site](https://img.shields.io/badge/Output-Static_Site-315EFB)](https://geoqiao.me/)
[![MIT License](https://img.shields.io/badge/License-MIT-22C55E)](LICENSE)

**[English](README_en.md)** · **[线上站点](https://geoqiao.me/)** · **[快速开始](#-快速开始)** · **[维护者入口](docs/dual-repo-architecture.md)**

</div>

## 为什么用 escaping？

| 你需要的 | escaping 提供的 |
| --- | --- |
| 专心写作 | 在 Issue 中写标题和 Markdown 正文，用标签决定是否发布；front matter 可选 |
| 一个完整的个人站 | 首页、文章归档、短想法、自选项目、关于页、标签、RSS、404 页、静态站内搜索与搜索引擎发现文件 |
| 简单的默认外观，也能改 | 内置 Quiet；改选项、只覆盖一个文件，或写一个完整 Theme |
| 可控的发布 | 某个 Issue 有错只跳过它并指出编号，其余照常发布；构建失败不影响线上站点 |

## 🚀 快速开始

使用 [escaping-template](https://github.com/geoqiao/escaping-template) 的 **Use this template** 创建站点，无需本机 Python、PAT 或手动创建发布标签。

> **公开预览：** 0.4.0 的 Action 和 starter workflow 已在本地测试中运行；在 GitHub 上从模板新建仓库的完整流程尚未验证。

1. 创建 `username.github.io`（免费账户使用公开仓库），保持 Issues/Actions 开启，在 **Settings → Pages** 把 **Source** 设为 **GitHub Actions**。
2. 保存一个带标题和 Markdown 正文的 Issue。workflow 的 `labels` 任务会在首次运行时创建发布标签；看不到时刷新 Issue 页面。
3. 添加一个 `type:blog`、`type:idea` 或 `type:about`，准备好后添加 `published`，在 Actions 中查看部署结果。

workflow 通过 `uses: geoqiao/escaping@v0.4.0` 调用生成器，站点仓库里不需要任何脚本。
仓库也可以不叫 `username.github.io`：这时网站在 `username.github.io/仓库名/` 下，escaping 会自动处理这个子路径。
详细操作、版本与失败恢复以[模板说明](starter/README.md)为准。

## 日常写作

| 操作 | 结果 |
| --- | --- |
| `type:blog` + `published` | 发布文章，进入 Blog、RSS 和对应的标签归档 |
| `type:idea` + `published` | 发布一条独立短想法；不进入 Blog 或 RSS，标签仅作展示 |
| `type:about` + `published` | 提供关于页；没有 About Issue 时显示公开个人资料 |
| 编辑已发布 Issue | 下一次成功构建更新站点；后续编辑以 GitHub Issue 为准 |
| 移除 `published` | 下一次成功构建撤稿；仅关闭 Issue 不会撤稿 |

只发布允许作者的内容；workflow 执行者不会自动获得作者权限。
Blog 用 `tag:python`、`tag:机器学习` 这样的标签分类；大小写不同、空格和下划线写法不同的算同一个标签。
文章缺省地址为 `/blog/{issue_number}/`。需要自定义 slug、摘要或原始创作日期时，可逐字段添加 front matter；已发布的 slug 应保持稳定。
完整规则与示例见 [Issue Content v1](docs/contracts/issue-content-v1.md)。

某个 Issue 有错（例如标签写法不合法）时，只有它被跳过，其余内容照常发布；这次运行标记为失败，
摘要里写明是哪个 Issue、该怎么改。

## 按需配置

模板的 `config.yaml` 从 `{}` 开始，仓库和 GitHub 个人资料会补上标题、作者、URL、头像和简介。
Config 分两层：站点字段（如 `site`、`profile`、`projects`）换了主题仍然有效；外观选项写在
`theme.options` 下，由所选 Theme 决定有哪些。

```yaml
site:
  title: 我的笔记
  language: zh # 同时让 Quiet 的界面文字显示中文
theme:
  use: quiet
  options:
    tagline: 写工具，也写学习
    featured_posts: [12, 7]
```

| 想调整的内容 | 入口 |
| --- | --- |
| 标题、个人资料、自选项目 | [配置示例](config.example.yaml)与[字段来源](docs/site-inputs.md)；示例不是必填清单 |
| 导航 | 默认 Home、Blog、Projects、Tags、About、RSS；Ideas 可显式加入。`site.navigation.items` 整体替换菜单，可设为 `[]`；见[配置来源](docs/site-inputs.md#missing-field-sources) |
| 外观 | 见下方“换外观” |
| 社交预览图 | 在 `seo.social_image` 配置 HTTPS 或 Theme 资源 URL（如 `/assets/images/og.png`）；Quiet 会输出 Open Graph/Twitter 图片标签 |
| 评论 | 默认关闭；设置 `comments.enabled: true`，并另行完成 [Utterances App 授权](https://github.com/apps/utterances)；Profile About 永远无评论 |
| 本地构建 | 需要 Python 3.14.x 和 uv；有 Token 时直接读 Issues，没有 Token 可用 `--issues-json` 离线构建，见[本地构建步骤](docs/site-inputs.md#local-build) |

写错字段名会报错并提示正确写法；0.1 的旧字段会告诉你移到了哪里。报错不会回显你填的值。
组织所有的内容仓库须显式配置 `github.allowed_authors`。
输出目录和本地 Theme 路径以 Config 所在目录为根；预览时把输出目录当作网站根目录，不使用 `/output/` URL 前缀。

### 换外观

从简单到完整，三种方式：

1. **改 Quiet 的选项**：在 `theme.options` 里设置，例如 `tagline`、`featured_posts`、`accent_color`。全部选项见 [Quiet](docs/themes/quiet.md)。
2. **只覆盖一个文件**：建一个 `theme/` 目录，放一个 `theme.yaml`（`api: 4` 和 `extends: quiet`）和你想替换的那个模板或静态文件，再设置 `theme: {use: ./theme}`。其余部分仍来自 Quiet。
3. **写一个自己的 Theme**：最少只要 `blog.html` 和 `post.html` 两个模板，见 [Theme 编写指南](docs/themes/authoring.md)。Theme 还可以声明自己的选项和界面文字。

也可以直接用别人放在 GitHub 上的 Theme：在 `config.yaml` 写 `theme: {use: github.com/作者/仓库/文件夹@v1.0.0}`，构建时自动下载这个版本，升级就改版本号。现有的 Theme 见 [Theme 列表](docs/themes/catalog.md)，用法见 [使用 GitHub 上的 Theme](docs/themes/authoring.md#using-a-theme-from-github)。

网站有哪些页面、地址是什么，由你博客仓库里的 `config.yaml` 决定：`pages` 可以关掉或挪动某个页面、加上 `/now/` 这样的额外页面，`redirects` 让旧地址跳到新地址。见 [页面](docs/site-inputs.md#pages)。

改完后运行 `escpe theme check --config config.yaml`：它用示例内容离线渲染每个页面，不需要 Token，并报告 Theme 的问题。

## 升级

站点在 workflow 的 `uses:` 一行固定生成器版本（tag 或完整提交 SHA），不会自动升级。
升级前先读 [CHANGELOG](CHANGELOG.md)；从 0.1 升级的步骤见其中的[升级说明](CHANGELOG.md#upgrading-from-01)，
本地 Theme 的改法见 [API 2 迁移说明](docs/themes/authoring.md#migrating-from-api-2)。
配置评论不等于验证评论写入；真实 App/OAuth 发帖仍需单独验收。

## 开发与维护

[维护者入口](docs/dual-repo-architecture.md)汇总架构、契约、测试和 ADR；Agent 使用 [AGENTS.md](AGENTS.md)。
站点 workflow 的写法以 [starter workflow](starter/.github/workflows/pages.yml) 为准，复制后由站点仓库维护；
生成器通过 [Action](action.yml) 运行。生成器升级、本地 Theme 迁移与生产部署是分开的操作。

## License

[MIT](LICENSE) © geoqiao
