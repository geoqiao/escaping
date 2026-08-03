---
slug: build-a-python-blog-on-github-pages
description: "背景"
created_date: "2024-05-12"
---

# 背景

我偶尔有写点什么的欲望，加上 yihong 老师 [gitblog](https://github.com/yihong0618/gitblog) 项目的激励，于是产生了写一个个人博客页面的想法。

因为工作上数据分析需要，我在 2022 年开始接触 Python。作为一名曾经试图考艺术硕士的商科生，我意外的很喜欢写 Python 的体验。很长一段时间以来，我只使用 Python 做一些数据分析工作。但随着使用时间的增长，我发现自己的 Python 代码代码虽然可以运行，但是很难读、很多代码重复使用率不高、维护起来很费力。

于是我尝试学习 Python 的基本概念，而不仅仅局限于 Pandas 和 sklearn。这个项目便是我目前学习的成果。

## why GitHub Pages

1. 不用买域名
2. 不用买服务器
3. 是一个网页，可以满足分享欲望

## why Python

实际上，GitHub Pages 提供了非常丰富的支持，也许使用 JavaScript 的框架可以更快更好的完成这个项目。但是，我只会写一点基础的 Python，其他语言完全不会。

# 思路

为了满足写博客的需求，我的思路非常简单：

1. 可以读取 GitHub Issues
2. 将读取到的 Issues 转换为 HTML
3. 有简单的 HTML 模板，有一个不丑的前端页面
4. 将渲染后的 HTML 上传到 GitHub Pages
5. 整个过程自动化，我只想写 issue，其他的工作全部自动完成

# 马上开干

## 读取 GitHub Issues

这个环节非常简单，GitHub 提供了一个非常简单使用的 Python 库：PyGithub。只需要设置好 GitHub Token，便可以很轻易的读取到 issues 的内容

```python
def get_all_issues(repo: Repository, me: str) -> PaginatedList[Issue]:
    """Get all issues for a given GitHub repository.

    Args:
        github_repo: GitHub repository name in the format "owner/name".

    Returns:
        List of GitHub issue objects.
    """
    issues = repo.get_issues(creator=me)
    return issues
```

返回的 issues 是一个包含所有 issue 的列表。通过`for循环`可以遍历这个列表，可以通过`issue.title`等方法获取 issue 的标题、创建时间、内容、tag 等信息。比如：

```python
issue.title # 获取标题
issue.updated_at # 获取创建时间
issue.body # 获取正文内容
```

## 将 issue 转换为 HTML

GitHub 有使用一个官方接口，可以将 markdown 格式的文本转换为 HTML，但是每次转换请求这个 API 的速度很慢，所以我使用了`marko`库。

`marko` 提供了 GitHub 风格的转换方法，只需要传入我们读取到的 issue.body 即可：

```python
from marko.ext.gfm import gfm

def markdown2html(mdstr: str):
    html = gfm.convert(mdstr)
    return html
```

## HTML 模板

我对于 CSS 和 JavaScript 一窍不通，所以这部分内容我是参考了 yihong 老师的 [GitHub Pages](https://yihong0618.github.io/gitblog/)，从页面的 HTML 源码中发现了可用的 CSS 和 JavaScript 代码，并且模仿页面的 HTML，这样拼凑出来的一个页面。

这个页面满足了我对于一个不太丑的前端页面的需求，并且因为过程中自己拼凑了模板，对于一些 CSS、JavaScript 的作用也有了一点点理解。

当然，这个模板的搭建过程中 [perplexity](https://www.perplexity.ai) 帮了我非常多的忙。`perplexity`非常强大，可以将我得到的前端代码作为文件上传，ai 帮我解读每个 CSS 和 JavaScript 的作用。免费版本已经足够我的使用，非常推荐！

## GitHub Actions 自动化

在主体代码全部实现后，接下来就是将整个过程自动化。这一步可以交给强大的 GitHub Actions 完成。它会帮我监控 issue 的变化：一旦有 issue 添加、编辑等动作，actions 会帮我自动执行我的 Python 代码，并将输出的 HTML 文件上传至 GitHub Pages 仓库。

这一步也主要参考 yihong 老师`gitblog`项目的 action 实现。因为我是用 [rye](https://github.com/astral-sh/rye) 管理 Python 项目，但`rye`并不支持输出`requirements.txt`，所以我增加了一条将`requirements.lock`文件转换为`requirements.txt`的命令：

```shell
sed '/^-e/d' requirements.lock > requirements.txt
```

## 总结

因为白天上班比较忙，所以每天晚上下班都会花一个小时来看这个项目。花了将近一个月的时间，我终于实现了自己搭建博客页面的想法。

现在我已经开始使用自己的项目来写博客，这种体验真的很美妙。

这是我的[源代码仓库](https://github.com/geoqiao/github_blog)和[GitHub Pages](https://geoqiao.github.io/contents/)页面
