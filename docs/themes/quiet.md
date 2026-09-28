# Quiet

Quiet 是内置 Theme：以中性黑白为主，只用少量头像洋红点缀。

## 选择 Quiet

```yaml
theme:
  use: quiet
```

这也是默认值，不写 `theme` 就会用 Quiet。想改 Quiet 的部分模板或样式，见
[Theme 作者指南](authoring.md#2-extend-quiet)。

## 选项

在 `config.yaml` 的 `theme.options` 下设置：

```yaml
theme:
  options:
    tagline: 研究者 / 工具作者
    featured_posts: [41, 62]
    accent_color: "#2f6aa7"
```

| 选项 | 类型 | 默认值 | 作用 |
| --- | --- | --- | --- |
| `tagline` | string | 空 | 首页简介上方的一行字 |
| `featured_posts` | posts | `[]` | 首页“精选”列出的 Blog Issue 编号，按填写顺序显示。不存在的编号会被跳过，并给出 `THEME_OPTION_POST_MISSING` 警告 |
| `footer_text` | string | 空 | 页脚作者名旁的文字；为空时显示“感谢阅读。”（按站点语言） |
| `show_powered_by` | boolean | `true` | 是否显示页脚的 “Powered by escaping” 链接 |
| `accent_color` | color | 空 | 浅色模式的点缀色，如 `"#a72f6a"`；为空时用 Quiet 自带的颜色 |
| `accent_color_dark` | color | 空 | 深色模式的点缀色，如 `"#e58bb6"`；为空时用 Quiet 自带的颜色 |
| `comments_theme` | choice | `github-light` | `comments_theme_mode: fixed` 时使用的 Utterances 配色。可选 `github-light`、`github-dark`、`preferred-color-scheme`、`github-dark-orange`、`icy-dark`、`dark-blue`、`photon-dark`、`boxy-light`、`gruvbox-dark` |
| `comments_theme_mode` | choice | `auto` | `auto` 跟随 Quiet 的浅色/深色模式；`fixed` 始终使用 `comments_theme` |

颜色值要加引号，否则 YAML 会把 `#` 之后当成注释。选项名写错或值不合法时，构建会失败并指出是哪个选项。
评论默认关闭，开启方法见[评论](authoring.md#comments)。

## 界面语言

Quiet 的界面文字有英文（`en`）和中文（`zh`）。按 `site.language` 选择：

- `zh`、`zh-CN`、`zh-TW` 等以 `zh` 开头的语言使用中文；
- 其他语言使用英文。

文章标题和正文不受影响，照 Issue 原文显示。想改某一句界面文字，可以在扩展 Quiet 的
Theme 里覆盖对应的 key，比如：

```yaml
api: 3
extends: quiet
strings:
  zh:
    footer_thanks: 谢谢来访。
```

全部 key 见 [`src/escaping/themes/quiet/theme.yaml`](../../src/escaping/themes/quiet/theme.yaml)。

## 可以替换的文件

在扩展 Quiet 的 Theme 里放一个同名文件，就会替换 Quiet 的那个文件。下面这些文件就是为此拆出来的：

| 文件 | 内容 |
| --- | --- |
| `head-extra.html` | 空文件，放在每页 `<head>` 末尾。适合加统计代码、字体或额外样式表 |
| `home-intro.html` | 首页标题下的简介：`tagline`、`profile.bio` 和指向 Blog、Projects、About 的一句话 |
| `header.html` | 首页右上角的按钮，以及其他页面的侧栏（头像、菜单、搜索、深色模式开关） |
| `footer.html` | 页脚：作者名、`footer_text`、`profile.links`、RSS 和 “Powered by” |
| `search.html` | 搜索对话框 |
| `components.html` | 共用宏：标签、文章列表、项目卡片、评论区、Mermaid 加载 |
| `base.html` | 所有页面的外框和 `<head>`。替换它会影响每一页 |
| `static/css/style.css` 等 | 静态文件同样按路径替换，比如 `static/images/favicon.png` |

用 `@quiet/` 可以在自己的文件里复用 Quiet 的原版，例如
`{% extends "@quiet/home.html" %}`。页面模板可以设置 `page_title`、`page_description`
和 `active_section`，`base.html` 会用它们生成标题、描述和当前菜单项，见
[Theme 作者指南](authoring.md#reusing-the-file-you-replace)。

## 设计说明

| 项目 | 约定 |
| --- | --- |
| 浅色 | 白色画布、近黑正文、中性灰侧栏和面板；链接 `#a72f6a`（可用 `accent_color` 修改） |
| 深色 | 中性近黑画布、近白正文；链接 `#e58bb6`（可用 `accent_color_dark` 修改） |
| 点缀色 | 洋红以 `#D2428A` 为参考，调整明度以满足 AA 对比度。首页显示 `profile.avatar`；其他页面的侧栏在没有头像时显示作者姓名首字母 |
| 首页 | 居中单栏，没有侧栏。简介里有指向 Blog、Projects、About 的链接。下面依次是精选文章（`featured_posts`，未设置时不显示）、最近 5 篇文章，以及最多 4 个 `featured: true` 的项目。文章列表只有标题和日期，详见[首页精选](../site-inputs.md#featured-writing-on-home) |
| 动效 | 首页入场、文字链接、背景树影和项目悬停用轻量 CSS。系统开启“减少动态效果”时停用动画和位移。禁用 JS 时内容和链接照常可用 |
| Blog | 归档页标题 16px、摘要 14px，保留日期和标签；没有摘要时不留空段落。Tag 页只显示标题、日期和标签 |
| 阅读 | 其他页面有固定侧栏、长文目录、代码复制按钮、移动菜单、键盘导航和评论加载失败时的替代链接 |
| 搜索 | 首页在右上角显示搜索和外观按钮；其他页面的搜索在菜单上方，手机上在 Menu 里。第一次打开时加载 `/search.json`，搜索已发布的 Blog、Idea 和项目的标题、摘要和标签（不搜全文）。标题匹配优先于标签和摘要；多个词须全部匹配；最多显示 20 条。支持 Ctrl/⌘ K、方向键、Tab 和 Esc，关闭后焦点回到打开它的按钮。加载失败时可以重试或去 Blog、Tags。禁用 JS、脚本缺失或浏览器不支持 `<dialog>` 时不显示搜索入口，其他导航照常可用 |
| 社交预览 | 设置了 `seo.social_image` 时，每页输出 `og:image`、`twitter:image`，卡片类型为 `summary_large_image`；`seo.social_image_alt` 不为空时再输出两个 `*:image:alt`。没设置时卡片类型为 `summary`，不输出图片标签 |
| 导航 | 默认菜单见[缺省值](../site-inputs.md#missing-field-sources)，Ideas 需要手动加入。自定义菜单会整体替换默认菜单；菜单为空时不显示 Menu 按钮，头像和外观开关仍在 |
| 评论 | 默认关闭。开启需要在配置里设置 `comments.enabled: true`，并给仓库安装 Utterances App。配色由 `comments_theme` 和 `comments_theme_mode` 决定。由个人资料生成的 About 页没有评论 |
| Idea 标签 | 显示为普通文字，不是链接，因为 Idea 没有标签页；Blog 标签仍链接到标签页 |
| 文章页尾 | Blog 文章底部显示“上一篇”（较新）和“下一篇”（较旧），范围是全部已发布的 Blog 文章；第一篇和最后一篇只显示一侧。Idea 和 About 没有这组链接 |
| Mermaid | 使用 `neutral` 配色。深色模式下只反相 SVG，打印时还原，不重新渲染；节点边框对比度至少 3:1 |
| 移动菜单 | 菜单不依赖正文增强脚本，也不会在首屏之后移出页面。禁用 JS 或 `appearance.js` 加载失败时菜单保持展开；`site.js` 加载失败时菜单仍能打开，按 Esc 关闭并回到按钮 |
| 紧凑目录 | 宽度 ≤1160px、启用 JS 且正文有 h1–h3 时，为目录预留空间；没有标题、禁用 JS 或打印时不预留。已知限制：脚本失败会留下一块空白（但不会出现点不了的按钮）；分段加载的 HTML 仍可能跳动；不支持 `:has()` 或 `scripting` 的浏览器会晚一点显示目录 |
| 外观偏好 | 读者手动选的浅色或深色保存在 `localStorage` 的 `quiet-theme` 里 |
| 打印 | 白底黑字；内容图片保留原色，SVG 用中性浅色 |

Mermaid 的配色适合 Quiet 自带的中性图表。作者自己写的 `classDef`、彩色图片和第三方内容，需要自行检查颜色含义和对比度。评论和 Mermaid 脚本由生成器统一提供，见
[静态文件与共享脚本](authoring.md#static-and-shared-assets)。
