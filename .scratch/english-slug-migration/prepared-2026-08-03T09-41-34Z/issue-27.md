---
slug: python-setup-with-uv-pdm-and-vscode
description: "前言"
created_date: "2024-11-03"
---

## 前言

写过好多次 Python 包管理工具和编辑器选择的 issues 了，但是很散，这里集中整合一下，一次性解决学习 Python 的新手一定会碰到的 Python 安装、环境配置、编辑器选择的问题！

### TL;DR

推荐使用`uv`或者`pdm`这样的工具来解决管理 Python 版本、管理虚拟环境及依赖的问题。

编辑器推荐使用 VSCode。

## 为什么要写这篇

我在学习 Python 之初遇到了三大难题：

### 1. 怎么下载 Python，用哪个 Python？

市面上的教程大部分让我们通过 Python 官网下载 Python 解释器，但是这对于新手来说有很多问题：

1. 要选择与教程匹配的 Python 版本：为了避免因为 Python 版本不同而出现的问题，但这并不容易，
2. 配置默认路径对新手来说不容易：下载后要配置路径，不然可能无法使用，这需要一些配置路径的知识
3. 如何切换 Python 版本：很多情况下，我们可能已经看了很多教程，电脑上已经安装了 Python，但是版本和当前教程并不一样！

我在接触 Python 的时候，经常卡在这第一步出问题，然后陷入找教程、看教程第一节、放弃、找下一个教程的死循环。

### 2. 怎么安装三方库，安装到哪里？

市面上的教程关于安装三方库的时候总是只说一句 `pip install` ，如果真的这么做了，时间久了之后，本机的 Python 环境一定会很混乱。

我主要学习 Python 来做数据分析工作，你懂的，数据分析的库贼多，而且互相之间大都有依赖关系。然后我有时还会想看些其他方面的教程，比如 Django、fastapi 这些。**我按照教程中不断的往本机环境`pip install` ，直到把新买的 MacBook 送进天才吧！**

### 3. 选择哪个编辑器？

这又是一大难题，好奇心作祟的我，遵循着差生文具多的定律，把几乎所有的主流编辑器都试用了：VSCode、jupyter notebook、PyCharm CE、spyder、zed、Neovim......

结果就是，只顾着看这种编辑器、折腾各种配置了，真正的 Python 代码怎么写是一点没看....

没有完美的编辑器！这里推荐：**VSCode，免费、功能强大、不局限于某个语言、跨平台、配置少、支持 jupyter notebook！**

不建议其他编辑器的原因：

1. jupyter notebook：除了在初学或者必要场景，不推荐使用。用 jupyter 写出来的代码结构性很差，会很难学会 Python 中面向对象的概念；如果入门之后切换到其他编辑器，也会增加切换编辑器的学习成本
2. PyCharm CE：专业版好贵，社区版居然不支持 jupyter notebook，太离谱。而且在我配置的过程中，感觉配置起来也相对麻烦，一直没有搞懂各种教程中对 PyCharm 吹捧的原因是啥
3. spyder：好喜欢这种左边`.py`文件，右边类似 jupyter 一样的输出展示！但是真的太慢了，功能界面也很老旧。而且 VSCode 也可以设置为类似 spyder 这样的界面
4. zed：性能真的好快！但是会陷入到 LSP 的各种配置文档中，不配置的话，甚至 impot 语句到会报错
5. Neovim：千万不要下载！千万不要下载！千万不要下载！时间一宿一宿的过去，根本不知道干啥了

## 实操 Python 环境配置-仅需五步进入代码学习

### 1. 安装 Python 项目管理工具

uv 和 pdm 二选一即可，这里以 macOS 为例：

```shell
# 安装uv
curl -LsSf https://astral.sh/uv/install.sh | sh
# or 安装pdm
curl -sSL https://pdm-project.org/install-pdm.py | python3 -
```

### 2. 安装 Python

```shell
uv python install 3.11 # 使用uv安装Python，我一般会把最近的4个版本都装上，方便折腾，反正也不会把电脑搞坏
```

### 3. 初始化项目并选择最低 Python 版本

给每个项目单独创建一个虚拟环境，并把项目文件放在一个文件夹内管理是一个非常好的习惯。比如，我会给我学习的每个教程都单独设置一个项目文件夹。

```shell
mkdir my_project # 创建文件夹，mkdir 是 make directory 的缩写
cd my_project # 进入我们创建的项目文件内，cd 是 change directory 的缩写

uv init . --python 3.9  # 使用uv初始化项目文件夹，并选择项目可接受的最低Python版本为3.9
```

### 4.选择 Python 版本并添加项目依赖

```shell
uv python pin 3.11 # 指定项目的Python版本，这里指定的版本不可以比初始化的最低版本低
uv add pandas # 使用uv安装pandas依赖，这时uv会自动帮我们把pandas安装到当前项目的虚拟环境中，如果我们没有安装3.11版本，uv会帮我们自动安装
uv add numpy scipy # 使用uv同时安装多个依赖
uv remove scipy # 使用uv移除scipy
```

`uv add`和`uv remove`每次运行都会帮我们自动进行依赖解析，安装最合适的三方库版本

### 5.VSCode 配置

这一步最简单，任何方式下载安装好 VSCode 之后，只需要下载 Python 插件，其他插件依据实际个人需求，比如中文界面、主题、csv 美化等等。如果想使用 jupyter 可以下载 jupyter 插件，然后在`.ipynb`文件中编辑即可

刚开始全部默认配置即可。VSCode 会自动帮我们完成虚拟环境识别、智能补全、错误提示等功能。

## 最后

类似 uv 和 pdm 这样的工具可以帮我们节省很多项目配置的时间，在正式学习 Python 之前先掌握他们的用法非常有必要。最后备注一些可能的疑问：

1. uv 和 pdm 有什么区别：
   - 功能上：基本功能完全一样，pdm 有更多的高级功能更加成熟一点
   - 性能：uv 基于 rust，在依赖解析方面更快
2. 如何生成`requirements.txt`文件：
   - uv：`uv export > requirements.txt`
   - pdm：`pdm export -f requirements > requirements.txt`
3. 每个项目一个环境，重复的依赖会不会特别占存储空间？
   - 不会，uv 和 pdm 都采用的中心化存储缓存，每个版本的包只有在第一次安装的时候存储一份，后续相同的版本会复用第一次安装的缓存
4. 文档：
   - uv：https://docs.astral.sh/uv/
   - pdm：https://pdm-project.org/en/latest/

最后再提一句，编辑器就用 VSCode 就行了，千万不要瞎折腾！千万不要瞎折腾！千万不要瞎折腾！
