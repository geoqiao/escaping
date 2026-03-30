# AGENTS.md

AI coding agents 的工作指南（双语项目，中文为主）。

## 项目概览

`github-blog` - Python 静态博客生成器，使用 GitHub Issues 作为 CMS。

**核心特性：**
- GitHub Issue 为博文，支持标签分类
- 全自动构建：Issue 更新触发 GitHub Actions
- PaperMint 主题（Hugo PaperMod 风格）
- SEO 友好：自动生成 sitemap、robots.txt
- 中文标题自动转拼音生成 URL

**在线示例：** https://geoqiao.github.io/

## 技术栈

- **Python**: >=3.9
- **包管理**: uv
- **GitHub API**: PyGithub
- **Markdown**: Marko (GFM + pangu)
- **类型检查**: ty
- **模板**: Jinja2
- **配置**: pydantic-settings
- **RSS**: feedgen
- **日志**: structlog

## 项目结构

```
src/github_blog/          # 主源代码
├── cli.py               # CLI 入口
├── config.py            # Pydantic 配置
└── services/
    ├── github_service.py    # GitHub API
    └── render_service.py    # 渲染、RSS、站点地图
templates/PaperMint/      # 默认主题
tests/                    # 测试文件
config.yaml              # 博客配置
```

## 核心命令

```bash
# 安装依赖
uv sync

# 运行测试（TDD 必备）
uv run pytest -v

# 本地生成
uv run blog-gen <TOKEN> <REPO>

# 本地预览（从项目根目录）
uv run python -m http.server 8000
```

## 关键配置

### 本地开发
**必须从项目根目录启动服务器**，不要从 `contents/` 启动：

```bash
# 正确
uv run python -m http.server 8000
# 访问 http://localhost:8000
```

原因：项目使用绝对路径 `/templates/PaperMint/static/...` 引用静态资源。

### 测试
```bash
# 运行所有测试
uv run pytest

# 特定测试
uv run pytest tests/test_config.py

# 带覆盖率
uv run pytest --cov=src --cov-report=term-missing
```

### 代码检查
```bash
# 代码检查
uv run ruff check .

# 自动修复
uv run ruff check --fix .

# 格式化
uv run ruff format .

# 类型检查
uv run ty
```

## TDD 开发流程（必须遵守）

**任何改动前，先写测试！**

```
写测试 → 运行失败 → 写代码 → 运行通过 → 重构
```

### 测试类型

| 改动 | 测试文件 | 重点 |
|------|---------|------|
| 新功能 | `tests/test_*.py` | 单元测试 |
| 改模板 | `tests/test_template_integrity.py` | CSS 类一致性 |
| 修 Bug | 对应文件 | 先写复现测试 |
| 重构 | `tests/test_cli.py` | 集成测试 |

## 开发规范

### Git
- 小步提交，方便回滚
- 避免频繁 `git commit --amend`
- 改动前查看历史：`git log --oneline -- 文件`
- 对比原始：`git diff HEAD~n -- 文件`

### 模板/CSS
- 检查现有样式：`grep "class=" 模板.html`
- 保持与 `.tag`, `.post` 等类一致
- 不确定时先询问设计意图
- 本地验证后再提交

### 路径处理
- 使用 `config.yaml` 配置
- 相对路径优先
- 避免 `Path.resolve()` 破坏原有逻辑

## 部署流程

GitHub Actions (`.github/workflows/gen_site.yml`)：

1. 触发条件：Issue 编辑、评论、push 到 main
2. 运行 `blog-gen` 生成静态文件
3. 复制到 `_site` 目录
4. 部署到 GitHub Pages

**必需环境变量：**
- `G_T`: GitHub Personal Access Token

## 经验教训

### 2026-03-31 URL Slug 重构

**问题**：改 `{number}-{tag}` 为 `{number}-{title}` 时出多个问题。

**根本原因**：
1. **没有先写测试**
2. **测试覆盖不足**：只检查内容存在，不检查 CSS 类

**教训清单**：
1. ✅ **TDD 优先**：先写测试再写代码
2. ✅ **查看历史**：`git log --oneline -- 文件`
3. ✅ **理解设计**：`git diff HEAD~n -- 文件`
4. ✅ **本地验证**：`uv run python -m http.server`
5. ✅ **谨慎重构**：不随意改原本工作的路径
6. ✅ **小步提交**：方便回滚

**改进**：
- `.claude/skills/my-coding-guidelines/SKILL.md` - TDD 检查清单
- `tests/test_template_integrity.py` - 模板完整性测试
- `.github/pull_request_template.md` - PR 强制检查

## 参考

- **详细指南**: `docs/detailed-guide.md`
- **TDD Skill**: `.claude/skills/my-coding-guidelines/SKILL.md`
- **PR 模板**: `.github/pull_request_template.md`
