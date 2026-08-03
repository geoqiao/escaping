---
slug: add-yaml-config-to-github-pages-blog
description: "好长一段时间了，工作上事情很多，很烦。也很久没有写工作以外的 Python 了。趁着假期和一些其他原因，今天又重新捡起了 github blog 这个项目。"
created_date: "2024-10-03"
---

好长一段时间了，工作上事情很多，很烦。也很久没有写工作以外的 Python 了。趁着假期和一些其他原因，今天又重新捡起了 [github_blog](https://geoqiao.github.io/contents/) 这个项目。

近期主要做了两个改动：

1.  把前端模板部分利用 `cursor` 重写了一下。和原来的 [even](https://github.com/ahonn/hexo-theme-even) 主题相比，现在的虽然看起来比较简陋，但胜在每一行 CSS 和 HTML 都知道是什么意思、有什么作用！

    >     其实过程特别简单，仅仅在 cursor 中使用了3个 prompt，cursor 太强大，几乎一遍过，所以这个改动真的没啥讲的。

2.  就是为主题增加配置文件的功能，目的是为了其他人使用（当然，大概率可能也没有其他人用），这也是写这篇 blog 要讲的主题。

## 正文

其实增加配置文件的功能想了很久，因为可以减少别人使用的成本，并且满足自己的虚荣心。

## why YAML？

其实这部分决策起来很快，主要有 4 个原因：

1. 我对与所有配置文件几乎都不熟
2. 记得 [Hugo](https://www.gohugo.org/doc/overview/configuration/) 的配置文件就可以用 YAML，GitHub Actions 也使用 YAML
3. JSON 太不易读了，对于小白来说那么多花括号会搞晕人的
4. TOML 看起来也挺复杂，而且我不想跟 Python 的`pyproject.toml`搞混

但 YAML 不是没有缺点：对缩进和空格有要求这一点比较麻烦，曾经我就因为这一点在 GitHub Actions 上浪费了一下午 debug。

**配置 YAML**：
目前我的配置还比较简单，模板中涉及的变量主要是博客的标题、描述、以及使用者的 GitHub 名称：

```yaml
# 博客信息
blog:
	title: GeoQiao's Blog
	description: This is a blog powered by pygithub and jinja2.
	url: https://geoqiao.github.io/contents
	author:
		name: geoqiao
		email: geoqiao@example.com

# GitHub 相关配置
github:
	name: geoqiao # GitHub 用户名
	repo: geoqiao/geoqiao.github.io # GitHub 仓库名称
```

使用 Python 读取 yaml 文件也很简单：

```python
import yaml  # 导入yaml包，需要提前安装`uv add pyyaml`

CONFIG_FILE = "./configs/config.yaml" # 配置文件路径

# 写一个上下文管理器打开就行，这个函数会返回一个配置文件的dict
def load_config():
	with open(CONFIG_FILE, "r") as file:
		config = yaml.safe_load(file)
	return config

CONFIG = liad_config()
```

读取文件之后，只要使用 dict 的方法读取相应的 value 就行，比如读取博客的标题就是：`CONFIG["blog"]["title"]`，这样就会输出所对应的 value`GeoQiao's Blog`。

## 剩下的

剩下的就比较简单了，只要 1. 在模板中把相应的变量用符合 Jinja2 的语法写入，2. 并把读取到的配置变量传入给 HTML 模板 即可

**写入模板**

把原本手写的标题、名字、描述部分全都换为变量格式：比如把 `geoqiao` 全部替换为`{{ github_name }}`

**给模板传入变量的值**

这里以渲染`index.html`为例:

```python
def render_blog_index(issues: PaginatedList[Issue]) -> str:
	env = Environment(loader=FileSystemLoader("templates"))
	template = env.get_template("index.html")
	# 通过CONFIG获取相应变量的value（就是字典取值的写法
	blog_title = CONFIG["blog"]["title"]
	github_name = CONFIG["github"]["name"]
	meta_description = CONFIG["blog"]["description"]

	return template.render(
		issues=issues,
		# 把取到的配置文件中的值传给HTML模板
		blog_title=blog_title,
		github_name=github_name,
		meta_description=meta_description,
	)
```

## 最后

配置文件功能增加后，使用这个项目搭建 GitHub Pages 博客会变得相对比较简单：

1. 新建一个 GitHub Pages 仓库，名字格式为`<github_name>.github.io`
2. 获取 GitHub Token（可以 Google 搜索如何获取
3. 把我的项目仓库中的文件全部复制到创建好的 GitHub Pages 仓库中
4. 修改`configs/config.yaml`中的配置项，将博客的标题、描述、GitHub 姓名全部改成自己的
5. 修改 GitHub Actions 中的仓库名字
6. 开始写 issue，submit 之后，GitHub Actions 会自动更新部署到页面
7. 到`https://<your_github_name>.github.io/contents`页面查看自己的文章

项目会自动生成 RSS feed，添加到诸如 netnewsfire 或 Follow 中，而且以上只需要配置一次，之后只需要每次写 issue 就好了

PS：当然现在的前端 templates 还比较简陋，我会慢慢更新优化，也欢迎随时 pull request 到[项目仓库](https://github.com/geoqiao/github_blog) 或者提交 issue 。
