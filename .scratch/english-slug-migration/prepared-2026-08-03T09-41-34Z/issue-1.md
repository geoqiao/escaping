---
slug: rye-python-package-manager-guide
description: "rye是一个 Python 的包管理器，可以更轻松的管理 Python 项目和虚拟环境，作者是流行 web 框架 flask 的作者Armin Ronacher"
created_date: "2024-01-06"
---

[rye](https://github.com/mitsuhiko/rye)是一个 Python 的包管理器，可以更轻松的管理 Python 项目和虚拟环境，作者是流行 web 框架 flask 的作者[Armin Ronacher](https://github.com/mitsuhiko)

作为一个刚开始学习 Python 的新手，它解决了我碰到的两个难题：

1. 使用`pip`安装包时，经常某些包无法在当前 python 版本安装
2. 不会使用 venv 等虚拟环境管理工具
3. 使用`conda`时，经常社区还没有适配某些最新版本的包

这里引出 rye 主要的几个功能：

1. 管理全局的 Python 版本
2. 管理虚拟环境中的 Python 版本
3. 以封装`pip`和`virtualenv`的方式，让我不必烦恼如何使用他们

## 安装 rye

在 macOS 上，直接运行一下命令即可，同时在 rye 的[文档](https://rye-up.com/guide/installation/#installing-rye)也给出了其他系统的安装方式。

例如 macOS：

> To install run you can curl a command which will install the right binary for your operating system and CPU architecture and install it:
>
> ````shell
> curl -sSf https://rye-up.com/get | bash
> ````

**补充**：

```shell
rye self update # 升级rye
```

```shell
rye self uninstall # 卸载rye
```

## 开始一个新项目

使用  `rye init`  初始化一个新项目非常容易。在这里，我开始一个名为： `"test-rye"`的新项目。

```shell
mkdir test-rye  #创建项目文件夹
cd test-rye #在终端进入刚才创建的项目文件夹
rye init . #使用rye初始化项目
```

执行初始化之后，rye 会帮我们创建一些默认文件：

```shell
tree
├── README.md       # 项目的README文件
├── pyproject.toml  # rye用来管理项目的文件
└── src
    └── test_rye
        └── __init__.py
```

现在，我们便可以安装自己想安装的包。假设我这个项目想用来做一些数据分析工作：

```shell
# 使用rye安装 numpy pandas scikit-learn xgboost
rye add numpy pandas scikit-learn xgboost # 解析包版本，并添加到pyproject.toml文件中
rye sync # 开始下载文件对应的包
```

至此，一个由 rye 管理的项目就创建完成了，我们可以使用 VSCode 打开项目文件夹，并开始写代码了。

```shell
code .  # 使用VSCode打开项目文件夹
```

此时，我们的项目文件夹结构如下：

```shell
tree
├── README.md
├── pyproject.toml
├── requirements-dev.lock
├── requirements.lock
└── src
    └── test_rye
        ├── __init__.py
        └── __pycache__
            └── __init__.cpython-311.pyc
```

**注意事项**：
当我们的项目需要添加新的依赖时，可以使用`rye add <package name>` 和 `rye sync`来安装对应的包，或者通过`rye romove <package name>`和`rye sync`来移除对应的包。

`rye add <package name>`和`rye romove <package name>`只修改`pyproject.toml`文件，`rye sync`会按照`pyproject.toml`文件实际对项目的依赖进行操作。

## 修改项目的 Python 版本

rye 当前为我们的项目安装 Python@3.11 版本，但不必担心，rye 为我们提供了修改项目 Python 版本的命令

```shell
rye pin 3.9
rye sync # 所有的修改都需要使用sync命令生效
```

此时，我们的项目的 Python 版本就变为了Python@3.9

## 全局 Python 脚本

某些情况下，有些包我们想要全局使用，比如`black`或者`ruff`来对我们的代码进行格式化。

```shell
rye install ruff
```

安装之后，就可以在终端全局使用`ruff`命令了

卸载也很简单：

```shell
rye uninstall ruff
```

## 最后

rye 还支持一些常规的操作，比如接管全局 python、升级项目中某个依赖或者所有依赖的版本、构建/发布包等等功能，可以通过[官方文档](https://rye-up.com/guide/)查看。
