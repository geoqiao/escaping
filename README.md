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
| 一个完整的个人站 | 首页、文章归档、短想法、自选项目、关于页、标签、RSS、静态站内搜索与搜索引擎发现文件 |
| 简单的默认外观 | 默认使用 Quiet，也支持站点自管的本地 Theme |
| 可控的发布 | 校验内容与链接；站点 workflow 只部署成功构建的产物 |

## 🚀 快速开始

使用 [escaping-template](https://github.com/geoqiao/escaping-template) 的 **Use this template** 创建站点，无需本机 Python、PAT 或手动创建发布标签。

> **公开预览：** 已验证现有生产站点的构建与部署；模板首次建仓、自动标签等完整新用户初始化尚未验证完成。

1. 创建 `username.github.io`（免费账户使用公开仓库），保持 Issues/Actions 开启，在 **Settings → Pages** 选择 **GitHub Actions**。
2. 保存带标题和 Markdown 正文的 Issue，等待 **Prepare missing labels only** 成功，再刷新标签选择器。
3. 添加一个 `type:blog`、`type:idea` 或 `type:about`，准备好后添加 `published`，查看 Actions 部署结果。

普通 project Pages 子路径不受支持；已有自定义域名须提供 HTTPS 根 URL。
详细操作、版本选择和失败恢复以[模板说明](starter/README.md)为准。

## 日常写作

| 操作 | 结果 |
| --- | --- |
| `type:blog` + `published` | 发布文章，进入 Blog、RSS 和适用的标签归档 |
| `type:idea` + `published` | 发布一条独立短想法；不进入 Blog 或 RSS，标签仅作展示 |
| `type:about` + `published` | 提供关于页；没有 About Issue 时可使用公开个人资料 |
| 编辑已发布 Issue | 下一次成功构建更新站点；后续编辑以 GitHub Issue 为准 |
| 移除 `published` | 下一次成功构建撤稿；仅关闭 Issue 不会撤稿 |

只发布允许作者的内容；workflow 执行者不会自动获得作者权限。
Blog 可使用 `tag:python` 这样的标签，缺省地址为 `/blog/{issue_number}/`。
若需要自定义 slug、摘要或原始创作日期，可逐字段添加 front matter；已发布 slug 应保持稳定。
完整规则与示例见 [Issue Content v1](docs/contracts/issue-content-v1.md)。

## 按需配置

模板的 `config.yaml` 从 `{}` 开始。只填写需要覆盖的字段，例如：

```yaml
site:
  title: 我的笔记
```

| 想调整的内容 | 入口 |
| --- | --- |
| 标题、个人资料、自选项目 | [配置示例](config.example.yaml)与[字段来源](docs/site-inputs.md)；示例不是必填清单 |
| 导航 | 默认 Home、Blog、Ideas、Projects、Tags、About、RSS；`site.navigation.items` 整体替换菜单，可设为 `[]`，品牌主页链接独立保留 |
| 外观 | [Quiet](docs/themes/quiet.md) 是唯一内置及默认 Theme；[本地 Theme](docs/themes/authoring.md) 使用 API 2，无远程自动下载 |
| 评论 | 默认关闭；设置 `comments.enabled: true`，并另行完成 [Utterances App 授权](https://github.com/apps/utterances)；Profile About 永远无评论 |
| 本地构建 | 需要 Python 3.14.x、uv 和可读取目标 Issues 的 Token，见[本地构建步骤](docs/site-inputs.md#local-build) |

组织所有的内容仓库须显式配置 `github.allowed_authors`。省略字段使用默认值，非法显式值会报错而非被忽略。
输出目录和本地 Theme 路径以 Config 所在目录为根；预览时将输出目录作为 HTTP document root，不使用 `/output/` URL 前缀。

以上描述当前源码；站点实际行为取决于选定的生成器版本。旧内置 `geoqiao.me`、`Escape1`、`Escape2` 已移除，显式选择会失败而不是静默换外观。
升级前按[移除主题迁移说明](docs/themes/authoring.md#migrating-removed-built-in-themes)切换 Quiet 或保留本地副本；旧 API、评论和菜单迁移见[迁移清单](docs/themes/authoring.md#migrating-from-api-1)。
配置评论不等于验证评论写入；真实 App/OAuth 发帖仍需单独验收。

## 开发与维护

[维护者入口](docs/dual-repo-architecture.md)汇总架构、契约、测试和 ADR；Agent 使用 [AGENTS.md](AGENTS.md)。
通用部署代码以 [starter workflow](starter/.github/workflows/pages.yml) 为准，复制后由站点仓库维护。
生成器升级、本地 Theme 迁移与生产部署是分开的操作。

## License

[MIT](LICENSE) © geoqiao
