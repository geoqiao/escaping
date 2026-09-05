# Quiet

Quiet 是独立内置 Theme：以中性黑白为主，只用少量头像洋红点缀。

```yaml
theme:
  source: builtin
  name: Quiet
```

默认 Theme 仍是 `geoqiao.me`。无需新增依赖或修改生产工作流；ThemeLoader 按包资源目录加载 Quiet。

| 项目 | 约定 |
| --- | --- |
| 浅色 | 白色画布、近黑正文、中性灰侧栏和既有面板；链接 `#a72f6a` |
| 深色 | 中性近黑画布、近白正文；链接 `#e58bb6` |
| 头像关联 | 洋红来自 Escape2 `author-mark.png` 的主体 `#D2428A`，调整明度满足 AA；不新增头像组件，不使用薄荷色 |
| 体验 | 固定站内索引、首页双栏、长文目录、代码复制、移动菜单、键盘导航与评论降级 |
| Idea 标签 | 显示为非交互文本，避免链接到不存在的 Blog tag archive；Blog 标签保持归档链接 |
| Mermaid | 既有本地 strict loader 使用 `neutral`；仅 SVG 在深色反相、打印还原，不重渲染；节点边框补足 3:1 |
| 主题偏好 | `quiet-theme` 保存读者明确选择的浅色或深色模式 |
| 打印 | Theme 表面白底、文字黑色；内容图片保留原色，SVG 使用中性浅色 |

Mermaid 的 CSS 配色方案适用于内置中性图表；作者自定义的 `classDef`、彩色图片和第三方内容需要另行检查其语义颜色及对比度。共享 `mermaid.js`、vendor runtime、comments 安全校验均未修改。

Config-relative 路径、canonical、RouteRegistry 和 staged publication 契约不变。
