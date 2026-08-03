# escaping

`escaping` 是一个 opinionated GitHub Issues personal-site generator。它将符合
[Issue Content v1](docs/contracts/issue-content-v1.md) 的 Issue snapshots 编译为不可变
`SiteModel`，统一生成 Home、Blog、Ideas、About、Projects、Tags、Atom、sitemap 和
robots，完整校验后再原子发布静态站点。

```text
GitHub Issue snapshots
  → ContentCompiler
  → SiteBuilder + RouteRegistry
  → SiteModel
  → RenderService
  → SiteArtifactValidator
  → OutputStagingService
```

## 页面与内容

| 内容 | canonical route |
| --- | --- |
| Home | `/` |
| Blog archive/detail | `/blog/`、`/blog/{slug}/` |
| Ideas | `/ideas/`、`/ideas/{issue_number}/` |
| About | `/about/` |
| Projects | `/projects/` |
| Tags | `/tags/`、`/tags/{tag}/` |
| Atom / sitemap / robots | `/atom.xml`、`/sitemap.xml`、`/robots.txt` |

Blog slug 来自 Issue front matter，不从标题推导。About 由不可变 Issue number 选择；
Markdown body 在移除 front matter 后经过 HTML allowlist sanitization。Ideas 和 Projects
是 v1 核心页面，不使用 feature plugin。

## 使用

复制并修改唯一的示例配置：

```bash
cp config.example.yaml /path/to/site/config.yaml
export GITHUB_TOKEN=...
uv run blog-gen --config /path/to/site/config.yaml
uv run python -m http.server 8000 --directory /path/to/site/output
```

命令可从任意工作目录执行。Config 中的本地 Theme 和 output 等相对路径始终以
**Config 所在目录**为根；`security.token_env` 动态决定读取哪个环境变量。

## Themes

`geoqiao.me` 是 wheel 内置默认 Theme；`Escape1`、`Escape2` 是内置可选 reference
Themes。Theme 配置可以省略，也可以显式声明：

```yaml
theme:
  source: builtin
  name: geoqiao.me
```

站点也可以使用 Config-relative 本地 Theme：

```yaml
theme:
  source: local
  name: my-theme
  path: theme
```

所有 Theme 必须满足 `theme.yaml` contract。`ThemeLoader` 只加载 package resources
或本地目录，不执行网络、Git fetch、cache 或 update。三个内置 Theme 共用生成器拥有的
`comments.js`，保留 Utterances 自动主题同步和 Safari lazy iframe 兼容处理。

## 仓库边界与部署

生成器仓库只拥有代码、`config.example.yaml` 和内置 Themes。真实站点仓库拥有：

- 真实 `config.yaml`；
- Pages workflow 与 `CNAME`；
- 如有需要，站点私有的本地 Theme。

Site Orchestrator 必须 pin 生成器 release 或完整 commit SHA，显式传入站点 Config，
并上传站点仓库下的 `output/` Pages artifact。生产 workflow 使用短期
`GITHUB_TOKEN`，不硬编码 PAT。详见 [Deployment contract](docs/deployment.md)。

## 开发与验证

```bash
uv sync
uv run pytest -q
uv run ruff check src/github_blog tests
uv run ruff format --check src/github_blog tests
uv run ty check
git diff --check
```

wheel consumer 测试会在源码目录之外构建代表性站点，验证 package resources、默认
Theme 和 Config-root 路径。预览时应将 `output/` 作为 HTTP document root，不要访问
`/output/` 前缀。旧 `.html` Blog URL 不生成 alias 或 redirect，见
[ADR-0003](docs/adr/0003-drop-legacy-html-urls.md)。
