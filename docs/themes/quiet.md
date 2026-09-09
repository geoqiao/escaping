# Quiet

Quiet 是唯一内置 Theme：以中性黑白为主，只用少量头像洋红点缀。

```yaml
theme:
  source: builtin
  name: Quiet
```

省略 Theme 配置也会选择 Quiet。公开接口与兼容规则见 [Theme API 2](authoring.md)，
旧本地 Theme 与站点默认变化见其[迁移清单](authoring.md#migrating-from-api-1)。

| 项目 | 约定 |
| --- | --- |
| 浅色 | 白色画布、近黑正文、中性灰侧栏和既有面板；链接 `#a72f6a` |
| 深色 | 中性近黑画布、近白正文；链接 `#e58bb6` |
| 点缀色 | 洋红以 `#D2428A` 为参考，调整明度满足 AA；使用已解析的 `profile.avatar`，无可用头像时显示作者首字母 |
| 体验 | 固定站内索引、首页双栏、长文目录、代码复制、移动菜单、键盘导航与评论降级 |
| 搜索 | 导航上方 Search 入口打开居中原生 dialog；手机位于 Menu 内。首次打开加载静态索引，匹配已发布 Blog/Idea 及项目的标题、摘要和标签（非全文）。标题优先于标签、摘要，多词须全部匹配；最多显示 20 条。支持 Ctrl/⌘ K、方向键、Tab、Esc，关闭后归还可见入口焦点。加载失败可重试或访问 Blog/Tags；禁 JS、缺失脚本或不支持 dialog 时不显示入口，原导航保留。无导航配置仍可使用独立搜索按钮 |
| 共享社交预览 | 配置 `seo.social_image` 时，在每个 HTML 页面输出 `og:image`、`twitter:image` 和 `summary_large_image`；非空 `seo.social_image_alt` 同时输出两种 `*:image:alt`。未配置时保持 `summary` 且不输出图片标签 |
| 导航与评论 | 默认 Home/Blog/Ideas/Projects/Tags/About/RSS；显式菜单整体替换，空菜单不生成开关，品牌与外观控制仍独立可用。评论默认关闭，启用须显式配置并另行授权 App；Profile About 永远无评论 |
| Idea 标签 | 显示为非交互文本，避免链接到不存在的 Blog tag archive；Blog 标签保持归档链接 |
| Blog 文章页尾 | 只显示全量已发布 Blog 中的英文 Previous（较新）/ Next（较旧）；首末和单篇不造链接，Idea/About 保留原页尾 |
| Mermaid | 既有本地 strict loader 使用 `neutral`；仅 SVG 在深色反相、打印还原，不重渲染；节点边框补足 3:1 |
| 移动导航 | 菜单不等待正文增强脚本，不在首屏后移出文档流。禁 JS 或 `appearance.js` 加载失败时保持展开；`site.js` 失败时仍可打开菜单、Escape 关闭并回归焦点 |
| 紧凑目录与已知限制 | ≤1180px、启用 JS 且正文含 h1–h3 时预留目录空间；无 heading、禁 JS 和打印不预留。脚本失败会留下空白（默认约 96px，含间距），但无伪可用控件。分段 HTML 仍可能跳动；不支持 `:has()` / `scripting` 的浏览器仍延迟显示目录 |
| 主题偏好 | `quiet-theme` 保存读者明确选择的浅色或深色模式 |
| 打印 | Theme 表面白底、文字黑色；内容图片保留原色，SVG 使用中性浅色 |

Mermaid 的 CSS 配色方案适用于内置中性图表；作者自定义的 `classDef`、彩色图片和第三方内容需要另行检查其语义颜色及对比度。共享资源与评论安全边界见 [Theme 作者指南](authoring.md#static-and-shared-assets)。
