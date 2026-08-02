# escaping

`escaping` 是一个以 GitHub Issues 为内容源的 strict static Site Compiler。
它把符合 `docs/contracts/issue-content-v1.md` 的 Issue snapshots 编译成
`SiteModel`，由一个 `RouteRegistry` 负责页面、输出路径、canonical、Atom、
sitemap、robots 和所有内部链接，然后在完整 artifact 校验通过后原子发布。

## v1 页面

| 内容 | canonical route |
| --- | --- |
| Home | `/` |
| Blog archive/detail | `/blog/`、`/blog/{slug}/` |
| Ideas | `/ideas/`、`/ideas/{issue_number}/` |
| About | `/about/` |
| Projects | `/projects/` |
| Tags | `/tags/`、`/tags/{tag}/` |
| Atom / sitemap / robots | `/atom.xml`、`/sitemap.xml`、`/robots.txt` |

Blog slug 来自 Issue front matter，不从 title 推导；Idea tags 只展示，不进入
Blog Tags taxonomy。About 由配置的 immutable Issue number 选择。body 会在
front matter 剥离后经过 Markdown 渲染和 HTML allowlist sanitization。

## 本地开发

```bash
uv sync
export G_T=ghp_xxx
uv run blog-gen
# 必须从仓库根目录启动，把 output 作为站点根目录
uv run python -m http.server 8000 --directory output
```

`security.token_env` 动态决定 token 环境变量名。strict build 要求
`theme_lock`；默认 `config.yaml` 使用 `geoqiao.me`，它以 Escape2 的终端视觉
语言为基线。Escape1、Escape2 和 geoqiao.me 共享同一模板契约、comments 行为、
canonical origin `https://geoqiao.me` 和 RouteRegistry 规则。

## 验证

```bash
uv run pytest -q
uv run ruff check src/github_blog tests
uv run ruff format --check src/github_blog tests
uv run ty check
git diff --check
```

生成站点后应检查 Home、Blog、Ideas、About、Projects、Tags、Atom、sitemap 和
robots。不要访问 `/output/`：站点根目录应直接映射到 `output/`，否则 `/blog/`、`/ideas/` 等根路由会 404。旧 `.html` Blog URL 不生成 alias 或 redirect，详见
`docs/adr/0003-drop-legacy-html-urls.md`。
