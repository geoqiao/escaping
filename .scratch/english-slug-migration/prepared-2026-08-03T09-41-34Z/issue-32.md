---
slug: vibe-coding-github-blog-with-trae
description: "TL:DR"
created_date: "2026-03-21"
---

## TL:DR

我使用 Trae IDE 对我的 github_blog 项目做了一些迭代。与之前不同的是，这次完全`vibe coding`，没有手写一行代码。

> 也许以后真的只需要自然语言编程，设置好明确的准出条件，剩下的就完全交给 AI 去做就好了。

## 为什么要迭代

正如项目`README.md`中所写：想要一个更好看的前端

### 一些背景

这个博客搭建在 GitHub Pages 上，由 Python、GitHub Actions 实现自动更新。

逻辑很简单：

1. 写 issue
2. GitHub Actions 捕捉每一次 issue 变更运行 python 脚本
3. python 读取 issues，并将 issue 渲染为 HTML(Jinja2)

但是有一个痛点：我不会写 JS 和 CSS。

所以第一版前端界面长这样：

<img width="1280" height="747" alt="Image" src="https://github.com/user-attachments/assets/6ad6413e-d305-4f91-a279-626be0fc9cb5" />

我当然很不满意呀！

## 怎么做

当然是让 AI 来帮我写前端！

### Why Trae ?

1. GitHub Copilot：我日常工作中 GitHub Copilot 基本可以满足需求，但是免费版额度不够
2. Cursor：相当明星的产品，但是我只试用过，没有付费
3. **价格**：刷到 Trae 的一些博客，性价比很高，只要 7.5$一个月
4. 至于其他比如 Claude Code：我确实不是职业开发，感觉价格很高，但是我很难物尽其用

### 过程

整个过程其实很简单，**给 Trae 一张图，然后让 Trae 自己改**，我只需要每次点击确认。当然我不希望它随意改动我的主体 python 代码，担心它搞砸主体逻辑。

1. 10min 不到，整体的模板框架已经出来了，
2. 然后就是字体、颜色、暗黑模式、目录悬浮、缩进等等一些小需求的顶点优化
3. 回头一看，不到 2 个小时，前端就变成了下面这样，大呼牛逼 👍

<img width="3024" height="1964" alt="Image" src="https://github.com/user-attachments/assets/731f4455-f8d2-477e-8b12-fd0ec02acd46" />

## 回顾

### 自己确实落伍了

Trae 只是一个普通的 AI 编程工具而已，看风评远没有 Claude Code、Codex 等产品优秀。然而已经可以理解本地项目，并写一个符合项目规范的前端模板。

### 核心永远是：上下文和提示词

> 纯主观感受，不一定对

不管是 system prompt、还是 skills，本质上都是提示词工程，只不过在实现工程上变得更有巧思。让大模型可以读取特定的提示词，提升某方面的能力。

MCP 和 web search 可以通过工具调用的方式增加特定方面的上下文，让模型做的选择更加符合现状，而不是瞎猜。

### 痛点在回滚和环境隔离

虽然 Trae 已经有 sand-box 隔离，但是一旦它搞错，或者自己想回滚的时候，一些实际发生的命令是不可逆的。比如创建、删除文件。刚开始没有提醒它用`uv`，结果在系统 python 环境下，用`PIP`装了一堆乱七八糟的库.

这些终端命令实打实的运行在自己的系统上，风险真是很大。也许后面会演变出一个专门隔离 agent 的系统，直到项目完全符合准出才应用到生产环境？
