---
slug: build-a-github-blog-without-git-or-frontend
description: "“ People Die, but Long Live GitHub ” [gitblog]"
created_date: "2026-04-05"
---


> “**People Die, but Long Live GitHub**” -- [[gitblog](https://github.com/yihong0618/gitblog)]

# Escaping 🚀

`Escaping` (https://github.com/geoqiao/escaping) 是一个极致简洁、自动化程度极高的个人博客框架。它将 GitHub Issues 作为后端编辑器，利用 GitHub Actions 自动触发构建，并最终通过 GitHub Pages 进行分发。

**核心特性**：

- 📝 **以 Issue 为博文**：直接在 GitHub Issues 中写作，支持标签分类。
- 🤖 **全自动化流**：无需本地部署，Issue 更新即刻触发自动构建。
- 🎨 **优雅 UI**：内置精美的 BearMinimal 主题，支持暗色模式。
- 🔍 **SEO 友好**：自动生成 `sitemap.xml`、`robots.txt` 以及语义化的 URL (Slugs)。
- ⚡ **性能卓越**：基于 Python 3.11 和 `uv` 构建，生成速度极快。

---

## 工作原理

```
┌─────────────────────────────────────────────────────────────┐
│ escaping (代码仓库 - 所有源码在这里维护)                      │
│                                                             │
│ ├── src/                  # Python 源代码                   │
│ ├── templates/            # 主题模板 (BearMinimal)           │
│ ├── .github/workflows/    # CI/CD 工作流                    │
│ └── config.yaml           # 博客配置                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ gen_site.yml
                              │ (生成网站并推送)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ geoqiao.github.io (内容仓库 - 仅存放 Issues)                  │
│                                                             │
│ ├── Issues              # 博客文章                          │
│ └── .github/workflows/  │                                   │
│     └── trigger.yml     │ 监听 Issues 事件                  │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ trigger.yml
                              │ (Issue 更新时触发)
                              │
                     ┌────────┴────────┐
                     │   GitHub Issues  │
                     │  (你的编辑器)    │
                     └─────────────────┘
```

---

## 如何使用

```
创建 Issue (添加标签)
        │
        ▼
┌─────────────────┐     dispatch      ┌─────────────────┐
│ geoqiao.github.io│ ──────────────→  │  escaping       │
│ trigger.yml     │                  │  gen_site.yml   │
└─────────────────┘                  └────────┬────────┘
                                               │
                                               │ git push
                                               ▼
                                      ┌─────────────────┐
                                      │ geoqiao.github.io│
                                      │ main 分支        │
                                      └────────┬────────┘
                                               │
                                               ▼
                                      ┌─────────────────┐
                                      │  GitHub Pages   │
                                      │  自动部署 ✓      │
                                      └─────────────────┘
```

1. **Fork 仓库**：Fork `escaping` 到你的 GitHub 账号
2. **配置 GitHub Pages**：
   - 进入 `Settings -> Pages`
   - Source 选择 **Deploy from a branch**
   - Branch 选择 **main**，Folder 选择 **/ (root)**
3. **添加 Secret**：
   - 在 `Settings -> Secrets and variables -> Actions` 中添加 `G_T`
   - 值为你的 [[GitHub Personal Access Token](https://github.com/settings/tokens)](https://github.com/settings/tokens)（需要 `repo` 和 `workflow` 权限）
4. **修改配置**：编辑 `config.yaml` 中的博客信息
5. **开始写作**：在仓库的 Issues 中创建文章，添加标签，稍等片刻博客就上线了

---

## 致谢

本项目深受以下优秀项目的启发：

- [[gitblog](https://github.com/yihong0618/gitblog)](https://github.com/yihong0618/gitblog) - 开启了 Issue 写作的先河。
- [[Gmeek](https://github.com/Meekdai/Gmeek)](https://github.com/Meekdai/Gmeek) - 提供了极简的构建思路。

## 最后

去年 11 月搬家，新出租屋离地铁站远了不少。电瓶车充电麻烦，于是买了辆二手自行车代步。

提车第二天早上，本来只想骑到地铁站。结果手脚不受控制，满脑子兴奋，直接骑到公司了——真的很解压。

这辆二手自行车是捷安特的 Escape 1 ，也是项目名字 Escaping 的由来。

---

_Tags: [#blog](https://github.com/geoqiao/geoqiao.github.io/issues/new#blog) [#github](https://github.com/geoqiao/geoqiao.github.io/issues/new#github) [#python](https://github.com/geoqiao/geoqiao.github.io/issues/new#python) [#escaping](https://github.com/geoqiao/geoqiao.github.io/issues/new#escaping) [#escape](https://github.com/geoqiao/geoqiao.github.io/issues/new#escape)_