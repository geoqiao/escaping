<div align="center">

<img src="https://raw.githubusercontent.com/geoqiao/escaping/main/docs/assets/escaping-logo.png" alt="escaping logo" width="180">

# escaping

**在 GitHub Issues 写作，得到一份整理好的 Markdown，交给任何建站工具。**

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![GitHub Issues](https://img.shields.io/badge/Content-GitHub_Issues-181717?logo=github)](https://docs.github.com/issues)
[![MIT License](https://img.shields.io/badge/License-MIT-22C55E)](https://github.com/geoqiao/escaping/blob/main/LICENSE)

**[English](https://github.com/geoqiao/escaping/blob/main/README_en.md)** · **[线上站点](https://geoqiao.me/)** · **[快速开始](#-快速开始)** · **[维护者入口](https://github.com/geoqiao/escaping/blob/main/docs/dual-repo-architecture.md)**

</div>

## escaping 做什么

`escaping` 只做一件事：把一个仓库里已发布的 Issue 写成 Markdown 文件。

| 层 | 谁负责 | 由什么规定 |
| --- | --- | --- |
| 内容 | 你在 Issue 里写，用标签决定是否发布 | [Issue Content v1](https://github.com/geoqiao/escaping/blob/main/docs/contracts/issue-content-v1.md) |
| 导出 | `escaping-site export` 筛选、校验，把每个值解析好，写成文件 | [Content Export v1](https://github.com/geoqiao/escaping/blob/main/docs/contracts/content-export-v1.md) |
| 网站 | 读这些文件的站点代码，也就是主题 | 站点自己 |
| 托管 | GitHub Pages、Cloudflare 或任何静态托管 | 站点自己 |

页面长什么样、网址怎么排、放在哪里，都不由 `escaping` 决定。

## 🚀 快速开始

**用默认主题。** 使用 [escaping-template](https://github.com/geoqiao/escaping-template) 的 **Use this template** 创建站点。模板里有一个读导出文件的默认主题和现成的 workflow，无需本机 Python 或 PAT。步骤以模板的 README 为准。

**自己写主题。** 任何能读 Markdown 的建站工具都可以。在 workflow 里运行：

```bash
uvx escaping-site@0.6.0 export --config config.yaml --output src/content
```

然后让你的站点读 `src/content`。文件格式见 [Content Export v1](https://github.com/geoqiao/escaping/blob/main/docs/contracts/content-export-v1.md)，workflow 的写法见 [Deployment](https://github.com/geoqiao/escaping/blob/main/docs/deployment.md)。

## 日常写作

| 操作 | 结果 |
| --- | --- |
| `type:blog` + `published` | 导出为 `blog/<slug>.md` |
| `type:idea` + `published` | 导出为 `ideas/<issue_number>.md` |
| `type:about` + `published` | 导出为 `about.md` |
| 编辑已发布 Issue | 下一次导出更新文件 |
| 移除 `published` | 下一次导出删除文件；仅关闭 Issue 不会撤稿 |

只导出允许作者的内容；workflow 执行者不会自动获得作者权限。
用 `tag:python`、`tag:机器学习` 这样的标签分类；大小写不同、空格和下划线写法不同的算同一个标签。
需要自定义 slug、摘要、创作日期或更新日期时，可逐字段添加 front matter；已发布的 slug 应保持稳定。

某个 Issue 有错（例如标签写法不合法）时，只有它被跳过，其余内容照常导出；命令以状态码 2 结束，
并写明是哪个 Issue、该怎么改。导出失败时，上一次的文件原样保留。

## 导出的文件

```text
src/content/
├── manifest.json
├── about.md
├── blog/<slug>.md
├── ideas/<issue_number>.md
└── .escaping-output
```

每个文件的 front matter 都是解析好的值（`issue_number`、`title`、`slug`、`description`、
`created_date`、`update_date`、`tags` 等），正文是你写的 Markdown 原文。
同样的 Issue 总是得到逐字节相同的文件，所以把这个目录提交进仓库时，只有内容真的变了才会产生提交。

## Config

`config.yaml` 里 `escaping` 只读三段，其余部分留给你的站点：

```yaml
github:
  repo: alice/site            # 在 GitHub Actions 上可省略
  allowed_authors: [alice]    # 个人仓库且有 Token 时可省略
about:
  issue_number: 42            # 可省略：取最早发布的 About Issue
security:
  token_env: GITHUB_TOKEN     # 默认值
```

写错这三段里的字段名会报错并提示正确写法；报错不会回显你填的值。

## 从 0.5 升级

0.6.0 起 `escaping` 不再生成网站：`build` 命令、Jinja 主题、Quiet 和 Action 都已移除。
已有站点把 workflow 留在 `geoqiao/escaping@v0.5.1` 就能继续照旧工作；要换到 0.6.0，
见 [CHANGELOG](https://github.com/geoqiao/escaping/blob/main/CHANGELOG.md#upgrading-from-05)。

## 开发与维护

[维护者入口](https://github.com/geoqiao/escaping/blob/main/docs/dual-repo-architecture.md)汇总架构、契约、测试和 ADR；Agent 使用 [AGENTS.md](https://github.com/geoqiao/escaping/blob/main/AGENTS.md)。

## License

[MIT](https://github.com/geoqiao/escaping/blob/main/LICENSE) © geoqiao
