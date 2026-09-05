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
| Blog 文章页尾 | 只显示全量已发布 Blog 中的英文 Previous（较新）/ Next（较旧）；首末和单篇不造链接，Idea/About 保留原页尾 |
| Mermaid | 既有本地 strict loader 使用 `neutral`；仅 SVG 在深色反相、打印还原，不重渲染；节点边框补足 3:1 |
| 移动导航初始化 | head 中的 `appearance.js` 先注册委托事件，再设置 `navigation-ready`；菜单不等待 `site.js`，不在首屏后移出文档流。禁 JS 或 head 脚本失败时保持展开导航；`site.js` 失败时菜单仍可打开、Escape 关闭并回归焦点 |
| 主题偏好 | `quiet-theme` 保存读者明确选择的浅色或深色模式 |
| 打印 | Theme 表面白底、文字黑色；内容图片保留原色，SVG 使用中性浅色 |

Mermaid 的 CSS 配色方案适用于内置中性图表；作者自定义的 `classDef`、彩色图片和第三方内容需要另行检查其语义颜色及对比度。共享 `mermaid.js`、vendor runtime、comments 安全校验均未修改。

Config-relative 路径、canonical、RouteRegistry 和 staged publication 契约不变。

## N4-L / F08 本地交接记录

2026-09-06，基于候选 `a33701a`，仅修移动导航初始化；未修改项目默认值或部署。

| 检查 | 结果 |
| --- | --- |
| 旧口径移动 lab，固定输入，每页 3 个独立 context | 导航 surface 从 `466.48 → 84px` 改为始终 `84px`；导航单次 shift `0.408077 → 0` |
| CLS 中位数：首页 / 订阅对比 / Pi 工作流 | `0.408417 → 0.000340` / `0.458082 → 0.101208` / `0.408554 → 0.051531` |
| A17 边界 | 订阅文章仍略超 `0.1`：剩余归因为既有 TOC 插入、图片与字体；不在本任务内改动，A17 整体验收仍待处理。上述为 lab 非 field CWV |
| 回归与环境 | Python 3.11 / 3.14 全量各 261 passed、无 skip；Ruff / format / ty / diff / lock 检查通过；定向 Chromium / WebKit 26.5 导航可用，未验证真机 Safari |
| 保持范围 | N4-A 相邻导航与 N4-C 评论回归通过；72 个 HTML 仅移除菜单按钮的 `hidden`，其他内容及共享评论资源不变 |

本 worktree 的 `.scratch/n4-l/` 保存失败测试、测量原始网络/console/shift、截图与交接明细，不纳入提交。性能探针隔离第三方评论，与 N4-C 协议回放及真实服务 smoke 不同；未执行后者。由编排者独立复核后集成，不代表完整项目计划或生产验收完成。
