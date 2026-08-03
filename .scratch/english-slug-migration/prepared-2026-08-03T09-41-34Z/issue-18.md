---
slug: my-vscode-setup-for-python
description: "VSCode 是一款由微软开发、非常流行的代码编辑器：功能强大、简单易用。"
created_date: "2023-12-10"
---

VSCode 是一款由微软开发、非常流行的代码编辑器：功能强大、简单易用。

## 为什么不是其他编辑器

可以编辑 Python 的编辑器很多，但是为什么选择 VSCode 呢？

**PyCharm**：太重了，并且是付费软件。社区版免费，但无法在 PyCharm 中使用 jupyter notebook。并且实话说，我感觉 PyCharm 的学习曲线相对陡峭(下载过一次，感觉配置起来没有 VSCode 简单)。

**jupyter notebook**：在最开始，我使用 notebook 工作，主要写一些处理 excel 的脚本。缺点是写代码聚焦于每个`cell`，每个`cell`都很有条理，但是整体看起来很乱。

**spyder**：我觉得 spyder 的界面是最适合使用 Python 来进行数据分析类工作的。左边用来写代码，右下角展示输出，右上角展示输出的图片。但是缺点是集成的功能比较弱。

**VSCode**：可以配置成 spyder 类似的界面，并且功能更加强大、配置起来也更加简单直观。

## 安装 VSCode

安装 VSCode 非常简单，可以直接在[官网](https://code.visualstudio.com/download)安装，跟大多数下载软件一样，直接下载就行。

如果你是 macOS、并且已经安装了 Homebrew，可以通过以下命令安装：

```shell
brew install visual-studio-code
```

## 安装插件

实际上 VSCode 本身只是一个文本编辑器，使它强大且流行的主要原因是强大的插件系统。通过不同的插件组合，可以把 VSCode 配置成几乎任何想要的集成开发环境。

因为我是一个初学者，并且只会写一些简单的 Python 脚本，这里主要针对 Python 进行 VSCode 配置。

我的插件列表：

1. **Python&Pylance**：微软官方开发的 Python 插件，可以提供语法高亮、自动补全、类型检查等强大功能。
2. **Jupyter**：集成 notebook，可以在 VSCode 中编辑执行`.ipynb`文件，体验不亚于在网页编辑。并且还享受 VSCode 的 Python 插件提供的功能。通过在 setting 中配置，可以在`.py`文件中通过`shift+enter`把代码让代码在 Jupyter 中执行。
3. **Rainbow CSV**：通过不同列的颜色高亮，让在 VSCode 里看 CSV 文件时更不费眼睛。
4. **Ayu**：个人最喜欢的 VSCode theme。
5. **Ruff**：Python 的 lint&format 工具，有类型检查个人感觉比 black 好用。需要在本地环境安装`ruff`。

## 编辑配置

在下载好插件之后，插件的有些功能需要在 VSCode 设置中开启，为了方便，我直接把设置的 setting.json 文件放在这里供参考：

```json
{

// editor basics

"editor.accessibilitySupport": "on",

"editor.fontFamily": "JetBrains Mono NL, MesloLGS NF", //字体部分需要下载相关字体

"editor.cursorBlinking": "solid",

"editor.defaultFormatter": "charliermarsh.ruff", // ruff插件的配置项

"editor.mouseWheelScrollSensitivity": 1,

"editor.mouseWheelZoom": true,

"editor.semanticHighlighting.enabled": true, //语义高亮

"editor.wordWrap": "on",

"editor.autoClosingBrackets": "languageDefined",



// python

"[python]": {

"editor.formatOnSave": true,

"editor.codeActionsOnSave": {

"source.fixAll": "explicit",

"source.organizeImports": "explicit"

},

"editor.defaultFormatter": "charliermarsh.ruff"

},

"python.languageServer": "Pylance",

"python.analysis.typeCheckingMode": "basic", //类型检查



// theme

"workbench.colorTheme": "Best Themes - Xcode Catalina Bold",

// audio

"audioCues.chatRequestSent": "off",

"audioCues.chatResponseReceived": "off",

"audioCues.chatResponsePending": "off",

"audioCues.clear": "off",

"audioCues.diffLineDeleted": "off",

"audioCues.diffLineInserted": "off",

"audioCues.diffLineModified": "off",

"audioCues.lineHasBreakpoint": "off",

"audioCues.lineHasError": "off",

"audioCues.lineHasFoldedArea": "off",

"audioCues.lineHasInlineSuggestion": "off",

"audioCues.noInlayHints": "off",

"audioCues.notebookCellCompleted": "off",

"audioCues.notebookCellFailed": "off",

"audioCues.onDebugBreak": "off",

"audioCues.taskCompleted": "off",

"audioCues.taskFailed": "off",

"audioCues.terminalCommandFailed": "off",

"audioCues.terminalQuickFix": "off",

"audioCues.volume": 40,

"workbench.iconTheme": "material-icon-theme",

"jupyter.interactiveWindow.textEditor.executeSelection": true,

"debug.console.fontSize": 15,

"editor.fontSize": 15,

"window.zoomLevel": 1,

}
```
