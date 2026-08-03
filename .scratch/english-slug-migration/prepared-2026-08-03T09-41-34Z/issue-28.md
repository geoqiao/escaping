---
slug: free-vscode-ai-with-ollama-groq-and-continue
description: "这篇 issue 展示通过配置 Ollama 和 Continue 扩展，为 VSCode 配置免费、本地的 AI 编程助手。"
created_date: "2024-11-16"
---

这篇 issue 展示通过配置 Ollama 和 Continue 扩展，为 VSCode 配置免费、本地的 AI 编程助手。

我在体验了 cursor 之后，立即寻找类似 cursor 的免费解决方案。最终发现使用 Continue 配置自定义的 API 是相对比较简单，且实用的方法。

> **Ollama**: 是一个开源框架，专为在本地机器上便捷部署和运行大型语言模型（LLM）而设计。使用 ollama 可以在自己的本地电脑上运行开源大模型。
>
> **Groq**: 是一家专注于人工智能芯片研发的公司，目前提供的 API key 是完全免费的
>
> **Continue**: 是一个 VSCode 的 AI 助手扩展，提供付费版本、免费但需自定义 API 两种方式配置自己要使用的 AI 模型。

## 方案一：使用 Ollama

### 安装 Ollama

Ollama 现在支持 Windows、Linux、macOS，是一个真正意义上的跨平台本地大模型解决方案，安装使用起来也比较简单。

```markdown
进入 Ollama [官网](https://ollama.com/)，点击 Download，即可完成下载安装
```

### 安装本地大模型

因为我的电脑内存为 16G，安装参数比较大的模型运行会比较慢，所以我这边推荐`qwen2.5-coder:7b` 或者 `codeqwen 7b`。

这两个模型的编程能力都比较强，并且参数只有 7b，运行在我的本地机器上还算比较流畅。

安装也比较简单，打开终端，每个模型大概不到 5G，运行命令后等待下载成功即可：

```bash
# 如果内存吃紧可以仅安装一个
ollama run codeqwen   # 安装 codeqwen
ollama run qwen2.5-coder:7b # 安装 qwen2.5-coder:7b
```

### 安装 Continue

在 VSCode 的扩展商店搜索 Continue 并安装。Continue 对新用户提供可免费试用，可以使用 Claude 和 ChatGPT 的最新模型。

### 修改 Continue 的配置文件

将这段 JSON 配置粘贴入 Continue 的 config.json 中，Continue 便会自动检测本地已经安装的大模型

```json
{
"title": "Autodetect",
"provider": "ollama",
"model": "AUTODETECT",
"systemMessage": "You are an expert software developer. You give helpful and concise responses.You will think in English and reply in Chinese"
},
```

## 方案二：使用 Groq-API

### 生成自己的 API key

打开官方的[API Keys 生成页面](https://console.groq.com/keys)，使用 GitHub 或者 Google 登录，然后直接点击`Create API Key`即可

### 配置 Continue

将这段 JSON 配置粘贴入 Continue 的 config.json 中，将 apikey 替换为自己的，Continue 便会自动检测 API 可以调用的大模型

```json
{
"model": "AUTODETECT",
"title": "Autodetect",
"apiKey": "<your API key>",
"provider": "groq",
"systemMessage": "You are an expert software developer. You give helpful and concise responses.You will think in English and reply in Chinese "
}
```

值得一提的是，groq 的生成速度非常快，而且支持调用 70b，甚至更大参数的模型，使用体验要比本地的 ollama 好上不少。

## 结论

现在给自己配置一个免费的编程助手真的不要太简单，虽然能力上还不如 Claude，但是日常使用已经非常够用了

<img width="1988" alt="image" src="https://github.com/user-attachments/assets/b257d01e-3c16-4a38-b75e-413d0ce500f8">
