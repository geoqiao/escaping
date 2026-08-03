# geoqiao.me visual directions — throwaway prototype

> PROTOTYPE — 这个目录只回答“下一版 geoqiao.me 应该长什么样”，不会接入生产主题。

三个结构不同的方向与一个 A 的精简分支放在同一个静态页面中，通过 `?variant=` 切换；`?page=` 用于检查不同内容页面。

## 运行

从仓库根目录执行：

```bash
uv run python -m http.server 4173 --directory .scratch/geoqiao-personal-site-v1/prototypes/visual-directions
```

打开：

```text
http://localhost:4173/?variant=ledger&page=home
```

A 的 Dark Mode 可直接打开：

```text
http://localhost:4173/?variant=ledger&page=home&mode=dark
```

A2「Quiet Ledger」的 Dark Mode：

```text
http://localhost:4173/?variant=quiet-ledger&page=home&mode=dark
```

- 底部 `←` / `→` 或键盘方向键切换视觉方向。
- 站内导航切换 Home、Blog、Ideas、Projects、Tags、About。
- 点击文章标题进入代表性的文章详情页。
- URL 参数会同步更新，方便直接分享某个视图。

## 设计问题

在保留当前内容契约——头像、简介、Blog、Ideas、Projects、Tags、About、RSS、文章日期与标签、代码、表格、评论——的前提下，哪一种视觉语言最适合“金融策略分析 + 工具折腾 + 生活记录”的个人站？

## A — Signal Ledger / 策略台账

### 设计系统

- **头像取色**：主要色簇为 Magenta `#e221a2`、Bright Pink `#f55fdd` 与 Emerald `#0d9970`；UI 只采用 Magenta，Emerald 保留在头像中。
- **Light 颜色**：Paper `#f7f7f5`、Surface `#ffffff`、Ink `#111113`、Muted `#6c6c70`、Coral Orange `#c4483a`。
- **Dark 颜色**：Paper `#0b0b0d`、Surface `#111114`、Ink `#f4f4f2`、Muted `#a0a0a4`、Coral Orange `#ff7768`。
- **主题色决策**：根据站点所有者的视觉比较，UI 回到第一版的 Coral Orange；头像继续保留其原始 Magenta / Emerald，不再强制让 UI 与头像同色。
- **主题色使用范围**：只用于头像偏移边、active navigation、current signal、focus/hover 和少量 code 状态；普通标签与结构说明回归灰阶。
- **模式切换**：A 的 header 提供 Light/Dark 控制，状态写入 `?mode=` 并在本次浏览器会话中记忆。
- **字体**：`Songti SC`（少量标题）、`PingFang SC`（正文）、`SFMono-Regular`（日期、标签、Issue 编号）
- **布局**：桌面端左侧 sticky identity rail，右侧是按时间排列的 ledger；文章页把左栏切换成目录与元数据。
- **Signature**：贯穿文章列表的“信号线”和状态点，来自策略监控台账，而不是装饰性时间线。

```text
┌ identity / role ┐  ┌ latest signal ────────────┐
│ avatar + bio    │  │ date  issue  article       │
│ links / project │  │  ·     ·      article      │
└─────────────────┘  └────────────────────────────┘
```

**优势**：中文长文最舒服；信息密度高但安静；实现成本最低。  
**风险**：个性来自细节和排版，第一眼冲击力较弱。  
**预计生产实现成本**：低—中。

## A2 — Quiet Ledger / 安静台账

这是对 A 的减法版本，用来回答“保留台账身份时，页面还能删掉多少视觉元素”。

- **保留的唯一 signature**：日期、真实 GitHub Issue 编号、Coral signal marker 与极细竖向 trace。
- **删除**：Hero eyebrow、Current Signal、列表序号、文章摘要、标签方框、列表横线、背景网格和文章页独立 metadata / TOC 侧栏。
- **布局**：首页桌面端采用 A 的完整 Profile rail，并将其移动到内容右侧；内页直接使用单列阅读布局；移动端隐藏 identity rail，让内容紧跟导航出现。
- **文章页**：`BLOG / ISSUE #41 → 标题 → 日期 / 阅读时长 / plain tags → 正文`，不再重复摘要与侧栏元数据。
- **配色与字体**：完全复用 A 的 neutral + Coral token 和 Songti / Sans / Mono 三种角色，不引入新颜色或字体。

```text
┌ two-line thesis ───────────┐  ┌ A profile rail ┐
│ date  · #41  article title │  │ avatar / role  │
│       · #36  article title │  │ bio / project  │
└─────────────────────────────┘  └────────────────┘
```

**预期**：主内容区明显减噪，移动端更快进入文章列表，Issue CMS 身份反而更集中。  
**取舍**：相比 A 少了“策略监控台”的叙事层次，但更适合长期阅读与内容增长。

## B — Workbench / 工具工作台

### 设计系统

- **颜色**：Midnight `#09111f`、Panel `#101b2e`、Text `#edf3ff`、Signal `#8ca8ff`、Mint `#72d7c2`、Muted `#8d9bb4`
- **字体**：`Avenir Next` / `PingFang SC`（内容）、`SFMono-Regular`（导航、路径、状态）
- **布局**：左侧 workspace rail、顶部路径栏、中央内容 pane、右侧 context pane；移动端按内容优先级折叠为单列。
- **Signature**：首页将最新文章中的 Pi → Herdr → Neovim 工作流画成一个小型 trace，而不是复刻普通 terminal prompt。

```text
┌ workspace ┐┌ path / status ────────────────────┐
│ Home      │├ main pane ───────┬ context pane ┤
│ Blog      ││ featured / list  │ now / tags   │
│ Projects  ││                  │ project      │
└───────────┘└──────────────────┴───────────────┘
```

**优势**：延续当前暗色技术气质，但层级更清晰；Projects / Ideas 有天然位置。  
**风险**：容易显得像产品后台；移动端和文章长读需要克制 pane 数量。  
**预计生产实现成本**：中—高。

## C — Issue Archive / 议题档案

### 设计系统

- **颜色**：Chalk `#f6f7f2`、Ink `#10131a`、International Blue `#1646d8`、Tangerine `#ef643f`、Lemon `#f1d657`、Grid `#bdc5d2`
- **字体**：`Arial Narrow` / `Avenir Next Condensed`（展示）、`PingFang SC`（正文）、`SFMono-Regular`（档案编号）
- **布局**：超宽 masthead + 全宽 issue index；内容不放卡片，使用大号 Issue 编号、粗分隔线与边缘栏目标签建立层级。
- **Signature**：`#41`、`#36` 等真实 GitHub Issue 编号成为站点的“馆藏编号”，直接表达 GitHub Issues CMS 身份。

```text
┌ GEOQIAO / ISSUE-BASED PERSONAL ARCHIVE ───────┐
├ #41 ─────────── latest feature ───────────────┤
├ #36  date   title                         tags ┤
├ #35  date   title                         tags ┤
└────────────────────────────────────────────────┘
```

**优势**：识别度最高，和站点技术来源有真实关联；长标题也能成为视觉资产。  
**风险**：最强势，生活类文章可能需要降低视觉噪声；文章详情必须切回更窄的阅读宽度。  
**预计生产实现成本**：中。

## 自检与取舍

- 没采用常见的暖米色 + 高对比 serif + 陶土色组合；Ledger 改成冷调“报告纸”，避免落入模板化 editorial。
- Workbench 没继续堆 terminal prompt，而是用工作区、路径和 trace 表达工具链。
- Archive 虽使用粗线和大字，但编号是内容的真实 Issue identity，不是无意义的报纸装饰。
- 三个方向均包含 `:focus-visible`、移动端布局和 `prefers-reduced-motion`。

## 风格参考（只提取原则，不复制页面）

- [Steph Ango](https://stephango.com/) — note-first 的内容组织和系统化配色。
- [Anthony Fu](https://antfu.me/) — Posts、Projects 与个人兴趣并列呈现。
- [Paco Coursey](https://paco.me/) — 克制的交互细节和界面型个人站。
- [Manuel Moreale](https://manuelmoreale.com/) — text-first、低噪声的 archive。
- [Julia Evans](https://jvns.ca/) — 技术内容也可以保留强烈的个人表达。

## 代表性数据

文章标题、日期、标签、About 文案来自公开的 `geoqiao/geoqiao.github.io` Issues；Projects 使用公开的 `geoqiao/escaping` 仓库信息。Ideas 当前没有已发布内容，因此 demo 特意保留真实空状态。
