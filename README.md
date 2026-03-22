# github-blog 🚀

[English](#english) | [简体中文](#简体中文)

---

## 简体中文

### 简介

`github-blog` 是一个极致简洁、自动化程度极高的个人博客框架。它将 GitHub Issues 作为后端编辑器，利用 GitHub Actions 自动触发构建，并最终通过 GitHub Pages 进行分发。

**核心特性**：

- 📝 **以 Issue 为博文**：直接在 GitHub Issues 中写作，支持标签分类。
- 🤖 **全自动化流**：无需本地部署，Issue 更新即刻触发自动构建。
- 🎨 **优雅 UI**：内置精美的 PaperMod 主题，支持暗色模式与极致的中西文排版优化。
- 🔍 **SEO 友好**：自动生成 `sitemap.xml`、`robots.txt` 以及语义化的 URL (Slugs)。
- ⚡ **性能卓越**：基于 Python 3.11 和 `uv` 构建，生成速度极快。

### 快速开始 (3步搞定)

1. **通过模板创建**：点击 `Use this template` 创建你的仓库（建议命名为 `username.github.io`）。
2. **配置秘钥**：在仓库 `Settings -> Secrets and variables -> Actions` 中添加名为 `G_T` 的 Secret，值为你的 [GitHub Personal Access Token](https://github.com/settings/tokens)。
3. **开始写作**：新建一个 Issue 并添加至少一个 Label，稍等片刻，你的博客就上线了！

### 示例

- **作者博客**: [geoqiao&#39;s Blog](https://geoqiao.github.io/)

### 鸣谢

本项目深受以下优秀项目的启发：

- [gitblog](https://github.com/yihong0618/gitblog) - 开启了 Issue 写作的先河。
- [Gmeek](https://github.com/Meekdai/Gmeek) - 提供了极简的构建思路。
- 感谢 **Trae/Gemini** 等 AI 工具在前端审美与代码重构上的巨大帮助。

---

## English

### Introduction

`github-blog` is a minimalist and highly automated personal blog framework. It turns GitHub Issues into a powerful CMS, leverages GitHub Actions for automated builds, and deploys via GitHub Pages.

**Key Features**:

- 📝 **Issue-based Writing**: Write directly in GitHub Issues with label support.
- 🤖 **Zero-Ops Workflow**: No local setup required; build triggers automatically on issue updates.
- 🎨 **Elegant UI**: Built-in refined PaperMod theme with dark mode and optimized typography for mixed CN/EN content.
- 🔍 **SEO Ready**: Automated generation of `sitemap.xml`, `robots.txt`, and human-friendly slugs.
- ⚡ **High Performance**: Powered by Python 3.11 and `uv` for lightning-fast site generation.

### Quick Start

1. **Use Template**: Click `Use this template` to create your repository (recommended: `username.github.io`).
2. **Add Secret**: Go to `Settings -> Secrets and variables -> Actions` and add a Secret named `G_T` with your [GitHub Personal Access Token](https://github.com/settings/tokens).
3. **Start Writing**: Create a new Issue and add at least one Label. Your blog will be live in seconds!

### Live Demo

- **Author's Blog**: [geoqiao&#39;s Blog](https://geoqiao.github.io/)

### Credits

This project is inspired by:

- [gitblog](https://github.com/yihong0618/gitblog) - The pioneer of Issue-based blogging.
- [Gmeek](https://github.com/Meekdai/Gmeek) - For the minimalist build philosophy.
- Thanks to **Trae/Gemini** for the incredible assistance in UI aesthetics and code refactoring.
