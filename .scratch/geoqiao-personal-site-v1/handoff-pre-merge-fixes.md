# Handoff: 修复 review 发现的 6 项合并前缺陷

## 背景

分支: `feature/geoqiao-personal-site-v1`（HEAD: `e0e20e9`）
四个独立 Codex GPT-5.6-SOL reviewer 完成了架构 / 健壮性 / 可用性 / 部署审查。
以下 6 项是剥离部署切换（Ticket 23/24）后，真正需要在合并前修复的缺陷。
第 7 项（Issue #41 的 Obsidian `![[...]]` 语法）由用户手动处理，不在本任务范围。

## 约束

- 只在 `feature/geoqiao-personal-site-v1` 分支工作；不要 push、不要 merge、不要修改 GitHub Issues、不要改动 `main`
- 遵循 `docs/agents/testing.md` 和 `AGENTS.md` 的 TDD 流程与代码风格
- 最小正确改动，不引入新抽象、新依赖、新配置
- 三个主题（Escape1、Escape2、geoqiao.me）共享同一套修改，用参数化测试，禁止复制测试矩阵
- 修完后必须全部通过：
  ```bash
  uv run pytest -q
  uv run ruff check src/github_blog tests
  uv run ruff format --check src/github_blog tests
  uv run ty check
  git diff --check
  ```
- 工作树保持 clean，小步提交，每个修复项一个 commit
- 不要触碰 `output/`（它是构建产物）；不要运行 `uv run blog-gen`（需要外部 token）

## 待修复项

### 1. 测试删除仓库根的真实 output/ 目录 [Blocker]

**问题**: `tests/test_cli.py:83` 和 `tests/test_cli.py:111` 在仓库根 `chdir`，并对真实 `_ROOT / "output"` 执行 `shutil.rmtree()`。跑一次 pytest 就删掉开发者的本地预览产物，违反 `docs/agents/testing.md` 的"目录误删"红线。

**修复**:
- 所有 SiteCompiler tracer 使用 `tmp_path`，把主题复制 / 注入临时仓库
- 验证仓库外 sentinel 在测试后仍存在
- 禁止测试引用 `_ROOT / "output"`

**文件**: `tests/test_cli.py`（可能涉及 `tests/test_site_integration.py`、`tests/test_output_staging.py`）

### 2. About 的 og:description / twitter:description 为空 [Major]

**问题**: 三个主题的 `about.html` 只覆盖普通 meta description；`og:description` 和 `twitter:description` 继承 `base.html` 的 `meta_description`（即空的 `site.description`），违反 `docs/contracts/issue-content-v1.md:210`。

**修复**:
- 三个 `about.html` 显式覆盖 `og_description` 和 `twitter_description` block，使用 About Issue 的 description
- 让 artifact validator 校验 About 页面三个 description 值一致
- 参数化三主题负向 / 正向测试

**文件**: `templates/geoqiao.me/about.html`、`templates/Escape1/about.html`、`templates/Escape2/about.html`、`src/github_blog/artifact_validation.py`

### 3. About / Idea 评论 "Loading..." 永不消失 [Major]

**问题**: `templates/geoqiao.me/post.html:174` 有 resize message handler 在评论加载成功后隐藏 loading；`templates/geoqiao.me/_comments.html` 没有这个逻辑。About（和未来 Idea）的 "Loading comments..." 会一直显示，即使 iframe 已加载。

**修复**:
- 把 Blog `post.html` 已有的可信 Utterances message 成功处理、resize / error / timeout fallback 逻辑集中到共享 `_comments.html`
- Blog / Idea / About 统一引用 `_comments.html`，仅由 `comments_issue_number` 参数化
- 保留 auto theme（postMessage + MutationObserver）、Safari lazy removal
- 三个主题同步

**文件**: `templates/geoqiao.me/_comments.html`、`templates/geoqiao.me/post.html`、`templates/geoqiao.me/idea.html`、`templates/geoqiao.me/about.html`，以及 Escape1 / Escape2 对应文件

### 4. Artifact validator 不检查 script src / img src [Major]

**问题**: `src/github_blog/artifact_validation.py:32` 的 `_HTMLProbe` 只收集 `<a>/<link href>`，不收集 `<script src>`、`<img src>`、`srcset`。删掉生成的 `prism.js` 仍返回 0 errors。同时跳过所有 absolute URL（包括 same-origin），导致 same-origin broken URL 也漏检。

**修复**:
- `_HTMLProbe` 采集 `script` / `img` / `source` 的 `src` 和 `img` 的 `srcset`
- same-origin absolute URL 转回 registry / asset lookup
- 增加负向测试：删除已引用 JS / image 必须失败
- 参数化三主题

**文件**: `src/github_blog/artifact_validation.py`、`tests/test_site_integration.py`

### 5. 移动导航键盘不可达 [Major]

**问题**: `templates/geoqiao.me/base.html:45`（及 override）用隐藏 checkbox + 不可聚焦 `<label>` 控制移动菜单，键盘用户无法打开。违反 `docs/themes/geoqiao-me-v1-baseline.md` 的 a11y 要求。

**修复**:
- 让 label 可聚焦（`tabindex="0"` + keyboard `Enter/Space` handler），或改用 `<button>` + `aria-expanded`
- 保留现有视觉行为和 hamburger 动画
- 三个主题同步

**文件**: `templates/geoqiao.me/base.html`、`templates/overrides/geoqiao.me/base.html`、`templates/Escape1/base.html`、`templates/Escape2/base.html`、对应 `static/css/style.css`

### 6. 移动端表格横向溢出 [Major]

**问题**: `templates/geoqiao.me/static/css/style.css` 没有给表格容器加 `overflow-x: auto`，长 URL 在移动端撑爆页面，出现整页横向滚动。`pre` / 代码块同理。

**修复**:
- 给 `table` 的父容器加 `overflow-x: auto`（或 `max-width: 100%` + `overflow-x: auto`）
- `pre` / 代码块已有处理的保持不变，确认不溢出
- 三个主题的 CSS 同步

**文件**: `templates/geoqiao.me/static/css/style.css`、`templates/Escape1/static/css/style.css`、`templates/Escape2/static/css/style.css`

## 接线来的后续任务（不在本次修复范围）

以下任务在本次 6 项修复完成后、合并后执行，不属于本 agent 职责：

1. **用户手动**: 修改 Issue #41 的 Obsidian `![[...]]` 图片语法为标准 Markdown
2. **合并**: 将 feature branch 合并到 `escaping/main`（用户操作）
3. **部署（Ticket 23）**: 在 `geoqiao.github.io` 站点仓库安装 `docs/deployment/geoqiao-pages.yml`，完成一次真实 Pages artifact 构建
4. **旧链路退役**: 确认新 workflow 成功后，删除两个仓库的 `G_T` secret 和旧 `trigger.yml`
5. **DNS / HTTPS（Ticket 24）**: 等 DNS 传播完成（已删除 Hostinger 旧 A 记录），启用 Enforce HTTPS
6. **线上 smoke**: 桌面 / 移动 / Safari 全页面验证，记录 cutover 证据
