---
slug: uv-python-project-management-guide
description: "uv 是什么"
created_date: "2024-09-08"
---

## uv 是什么

[uv](https://docs.astral.sh/uv/) 是一个 Python 项目管理和包管理的工具，由 Astral 开发（他们的另一个明星产品是 [ruff](https://docs.astral.sh/ruff/) ）。

在我刚接触 Python 的时候，阻止我动手写代码的问题主要有 2 个：

### 1. 怎么安装 Python？

确实，这是一个很大的问题。对于还不懂命令行的我来说，使用 Homebrew 或者官网下载的方式，都会污染我的电脑环境。以至于搞不清楚每次运行的 Python 到底是哪一个。

> 真实教训：因为想把自己安装的杂乱的 Python 都卸载掉，只保留 3.11 版本，导致我不小心删除了系统自带 Python 的某些文件，被迫将电脑送去天才吧维修！

### 2. 怎么安装三方库？

刚看了一些入门教程后，自以为这个不是问题，直接`pip install`就行了呗？

其实不然，安装的时候发现好多包安装不上：不适配当前的 Python 版本，或者存在三方库之间的依赖冲突。对初学者来说，又得了解一个新词汇：依赖解析。

再搜一圈教程下来，发现又要用`pyenv`管理 Python 版本，还得结合`pip`解决依赖冲突，命令行里面还得随时想着有没有激活虚拟环境！真服了，我可是刚入门的小白！

## uv - Python&依赖&项目管理

### 功能一：管理 Python 版本

uv 自带管理 Python 版本的功能，可以下载、项目中选用特定 Python 版本、卸载等全套服务，同时命令行操作也非常简洁：

```bash
uv python install 3.11.9   # 安装3.11.9版本的Python
uv python uninstall 3.11.9  # 卸载3.11.9版本的Python
uv python pin 3.11.9 # 为当前项目选择特定版本的Python
```

### 功能二：解决项目依赖

uv 提供`add`和 `remove`命令，可以为项目添加和删除依赖，非常直觉：

```bash
uv add pandas # 安装pandas库
uv remove pandas # 移除pandas库
```

## 为什么不选 conda or pdm

说实话 pdm 也是一个非常好用的 Python 项目管理工具，并且在最近的版本也可以管理 Python 版本，常用命令和 uv 基本一致。从我个人而言，有两个原因没有使用 pdm：

1. 功能太多（是的没错），兼容的标准很多，对我这个初学者而言会比较复杂
2. 无法真正独立于 Python 安装，自从曾经搞乱过系统 Python 环境后，我就再不想使用系统 Python 哪怕一丁点。所以，对我来说 uv 这种可以独立于 Python 安装，并且可以完全不使用系统 Python 建立项目的工具，完美满足我的需求

conda 是我第一个接触的 Python 管理工具，对我而言有几个小痛点：

1. 社区对于包的最新版本更新较慢：有时无法第一时间尝鲜某个新包的新功能（比如 pandas2.0 的 pyarrow 后端
2. 依赖解析慢且有一些小 bug：慢是显而易见的，bug 我没有仔细研究过，但之前经常碰到 wordcloud 库有时无法安装，有时又可以正常安装的问题（或许跟我刚开始不熟悉所以经常卸载重装有关

## 最后

这里只是介绍了 uv 的一些常用功能，对于如何使用大家可以参考[rye 推荐](https://geoqiao.github.io/contents/blog/1.html)以及[官方文档](https://docs.astral.sh/uv/)

如果你也是刚刚接触 Python，或者像我一样刚刚接触代码和命令行，非常推荐使用 uv，可以省去安装 Python 和相关依赖的绝大部分麻烦，直接进入主要的学习代码环节，而不是把时间浪费在环境配置上。
