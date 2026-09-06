# Quiet

Quiet 是独立内置 Theme：以中性黑白为主，只用少量头像洋红点缀。

```yaml
theme:
  source: builtin
  name: Quiet
```

Quiet 是默认内置 Theme，省略上述配置也会选择它。无需新增依赖；ThemeLoader 按包资源目录加载。
接口为 [Theme API 2](authoring.md)，旧本地 Theme 与站点默认变化见其迁移清单。

| 项目 | 约定 |
| --- | --- |
| 浅色 | 白色画布、近黑正文、中性灰侧栏和既有面板；链接 `#a72f6a` |
| 深色 | 中性近黑画布、近白正文；链接 `#e58bb6` |
| 头像关联 | 洋红来自 Escape2 `author-mark.png` 的主体 `#D2428A`，调整明度满足 AA；不新增头像组件，不使用薄荷色 |
| 体验 | 固定站内索引、首页双栏、长文目录、代码复制、移动菜单、键盘导航与评论降级 |
| 导航与评论 | 默认 Home/Blog/Ideas/Projects/Tags/About/RSS；显式菜单整体替换，空菜单不生成开关，品牌与外观控制仍独立可用。评论默认关闭，启用须显式配置并另行授权 App；Profile About 永远无评论 |
| Idea 标签 | 显示为非交互文本，避免链接到不存在的 Blog tag archive；Blog 标签保持归档链接 |
| Blog 文章页尾 | 只显示全量已发布 Blog 中的英文 Previous（较新）/ Next（较旧）；首末和单篇不造链接，Idea/About 保留原页尾 |
| Mermaid | 既有本地 strict loader 使用 `neutral`；仅 SVG 在深色反相、打印还原，不重渲染；节点边框补足 3:1 |
| 移动导航初始化 | head 中的 `appearance.js` 先注册委托事件，再设置 `navigation-ready`；菜单不等待 `site.js`，不在首屏后移出文档流。禁 JS 或 head 脚本失败时保持展开导航；`site.js` 失败时菜单仍可打开、Escape 关闭并回归焦点 |
| 紧凑目录初始化 | 屏幕宽度 ≤1180px、启用 JS 且正文含 h1–h3 时，CSS 为隐藏的闭合目录预留自然尺寸；初始化后显示原目录，换行不依赖固定占位高度。无 heading、禁 JS 和打印不预留；脚本失败会留下空白（默认约 96px，含间距），但无伪可用控件。分段 HTML 尚未解析到目录时仍可能跳动；不支持 `:has()` / `scripting` 的浏览器保留原延迟显示行为 |
| 主题偏好 | `quiet-theme` 保存读者明确选择的浅色或深色模式 |
| 打印 | Theme 表面白底、文字黑色；内容图片保留原色，SVG 使用中性浅色 |

Mermaid 的 CSS 配色方案适用于内置中性图表；作者自定义的 `classDef`、彩色图片和第三方内容需要另行检查其语义颜色及对比度。共享 `mermaid.js`、vendor runtime、comments 安全校验均未修改。

Config-relative 路径、canonical、RouteRegistry 和 staged publication 契约不变。
