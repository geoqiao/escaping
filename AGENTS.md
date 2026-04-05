# AGENTS.md

AI coding agents 的工作指南（双语项目，中文为主）。

## 项目概览

`escaping` 是一个基于 Python 的静态博客生成器，将 GitHub Issues 作为 CMS（内容管理系统）。

**核心特性：**
- 📝 **以 Issue 为博文**：直接在 GitHub Issues 中写作，支持标签分类
- 🤖 **全自动化流**：Issue 编辑/评论触发 GitHub Actions 自动构建
- 🎨 **PaperMint 主题**：Hugo PaperMod 风格，支持暗色模式
- 🔍 **SEO 友好**：自动生成 sitemap.xml、robots.txt、Atom RSS
- 🌐 **中文优化**：中文标题自动转拼音生成 URL slug
- ⚡ **高性能**：基于 Python 3.9+ 和 uv 构建

**在线示例：** https://geoqiao.github.io/

---

## 技术栈

| 组件 | 技术 | 用途 |
|------|------|------|
| 编程语言 | Python >=3.9 | 核心运行时 |
| 包管理 | uv | 依赖管理、虚拟环境 |
| GitHub API | PyGithub | 获取 Issues 数据 |
| Markdown | Marko (GFM + pangu) | Markdown 渲染 |
| 类型检查 | ty | 静态类型检查 |
| 模板引擎 | Jinja2 | HTML 模板渲染 |
| 配置管理 | pydantic-settings | YAML 配置解析 |
| RSS 生成 | feedgen | Atom 订阅生成 |
| 日志 | structlog | 结构化日志 |
| 重试机制 | tenacity | API 调用重试 |
| 中文转拼音 | pypinyin | URL slug 生成 |

---

## 项目结构

```
escaping/
├── src/github_blog/           # 主源代码
│   ├── __init__.py
│   ├── cli.py                 # CLI 入口，BlogGenerator 主类
│   ├── config.py              # Pydantic 配置模型
│   ├── models/                # 数据模型（预留）
│   ├── services/
│   │   ├── github_service.py  # GitHub API 封装
│   │   └── render_service.py  # 模板渲染、RSS、站点地图
│   └── utils/
│       └── slug.py            # URL slug 生成工具
├── templates/
│   ├── PaperMint/             # 默认主题（PaperMod 风格）
│   │   ├── base.html          # 基础母版模板
│   │   ├── home.html          # 主页模板
│   │   ├── index.html         # 博客列表页
│   │   ├── post.html          # 文章详情页
│   │   ├── tag.html           # 单个标签页
│   │   ├── tags.html          # 标签列表页
│   │   ├── about.html         # 关于页面
│   │   └── static/            # 静态资源（CSS/JS/图片）
│   ├── default_theme/         # 备用主题
│   └── seo/                   # SEO 模板（sitemap, robots）
├── tests/                     # 测试文件
│   ├── test_cli.py            # CLI 集成测试
│   ├── test_config.py         # 配置测试
│   ├── test_github_service.py # GitHub API 测试
│   ├── test_pagination.py     # 分页逻辑测试
│   ├── test_renderer.py       # 渲染服务测试
│   ├── test_slug.py           # URL slug 生成测试
│   └── test_template_integrity.py  # 模板完整性测试
├── config.yaml                # 博客配置（标题、URL、作者等）
├── pyproject.toml             # 项目配置、依赖、工具设置
├── main.py                    # 开发入口（调用 cli.py）
└── .github/workflows/         # GitHub Actions 工作流
    └── gen_site.yml           # 自动生成站点工作流
```

---

## 核心命令

### 环境设置

```bash
# 安装依赖
uv sync

# 激活虚拟环境
source .venv/bin/activate
```

### 本地开发

```bash
# 本地生成博客（需要 GitHub Token）
uv run blog-gen <TOKEN> <REPO>

# 示例
uv run blog-gen ghp_xxx geoqiao/geoqiao.github.io

# 本地预览（必须从项目根目录启动）
uv run python -m http.server 8000
# 访问 http://localhost:8000
```

⚠️ **重要**：必须从项目根目录启动服务器，不要从 `contents/` 启动。项目使用绝对路径 `/templates/PaperMint/static/...` 引用静态资源。

### 测试

```bash
# 运行所有测试
uv run pytest -v

# 运行特定测试文件
uv run pytest tests/test_config.py -v

# 带覆盖率报告（默认已启用）
uv run pytest --cov=src --cov-report=term-missing
```

### 代码质量检查

```bash
# 代码检查（lint）
uv run ruff check .

# 自动修复问题
uv run ruff check --fix .

# 格式化代码
uv run ruff format .

# 类型检查
uv run ty
```

---

## 配置说明

配置文件 `config.yaml` 使用以下结构：

```yaml
# 博客基本信息
blog:
  title: "Blog Title"           # 博客标题
  description: "Description"    # 博客描述（支持多行）
  url: https://example.com      # 博客 URL
  content_dir: "./contents/"    # 输出目录
  blog_dir: "blog/"             # 文章子目录
  rss_atom_path: "atom.xml"     # RSS 文件名
  author:
    name: "Author Name"
    email: "author@example.com"
  page_size: 10                 # 每页文章数

# GitHub 配置
github:
  name: username                # GitHub 用户名
  repo: user/repo               # GitHub 仓库名

# Google Search Console 验证
GoogleSearchConsole:
  content: "verification-code"
  verify: true

# 主题配置
theme:
  path: "templates/PaperMint"   # 主题路径
  seo: "templates/seo"          # SEO 模板路径
```

---

## TDD 开发流程（必须遵守）

**任何改动前，必须先写测试！**

```
写测试 → 运行失败 → 写代码 → 运行通过 → 重构
```

### 测试类型选择

| 改动类型 | 测试文件 | 测试重点 |
|---------|---------|---------|
| 新增功能 | `tests/test_*.py` | 单元测试，验证具体功能 |
| 修改模板 | `tests/test_template_integrity.py` | CSS 类一致性、模板文件存在性 |
| 修复 Bug | 对应模块的测试文件 | 先写复现测试，再修复 |
| 重构代码 | `tests/test_cli.py` | 集成测试，确保流程完整 |

### 测试示例

```python
# tests/test_new_feature.py
def test_new_feature_behavior():
    """描述期望的行为"""
    result = new_function(input_data)
    assert result == expected_output
```

---

## 代码风格规范

### Python 代码

- 使用 **双引号** 字符串（Ruff 强制）
- 使用 **4 空格** 缩进
- 行长限制 **忽略**（`E501` 规则禁用）
- 使用类型注解
- 使用 structlog 进行结构化日志

### Ruff 配置（pyproject.toml）

```toml
[tool.ruff.lint]
select = [
    "E", "W", "F", "I", "N", "UP", "B", "A", "C4", "SIM", "S", "RUF"
]
ignore = ["E501"]  # 忽略行长限制

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101"]  # 允许测试中使用 assert
```

### 模板/CSS 规范

- 检查现有样式：`grep "class=" templates/PaperMint/*.html`
- 保持与 `.tag`, `.post`, `.post-title` 等类一致
- 使用 `{{ theme_path }}` 变量引用主题路径
- 新样式必须在 `papermint.css` 中定义

---

## 安全考虑

1. **Token 安全**
   - GitHub Token 通过 GitHub Secrets (`G_T`) 注入
   - 禁止在代码中硬编码 Token

2. **输入验证**
   - 使用 Pydantic 模型验证所有配置
   - config.yaml 不存在时允许环境变量覆盖（用于 CI）

3. **XSS 防护**
   - Jinja2 模板启用 `autoescape=True`
   - RSS 内容使用 CDATA 包装

4. **依赖安全**
   - 启用 Ruff 的 `S`（bandit）规则检查安全问题

---

## 部署流程

GitHub Actions (`.github/workflows/gen_site.yml`)：

1. **触发条件**：
   - Issue 被创建或编辑
   - Issue 评论被创建或编辑
   - Push 到 main 分支
   - 手动触发 (workflow_dispatch)

2. **构建流程**：
   - 检出代码
   - 安装 uv 和 Python 3.11
   - 运行 `uv run blog-gen` 生成静态文件
   - 复制到 `_site` 目录
   - 部署到 GitHub Pages

3. **环境变量**：
   - `G_T`: GitHub Personal Access Token（必需）

---

## URL Slug 生成规则

格式：`{issue_number}-{slugified-title}`

- Issue number 保证 URL 稳定性和唯一性
- 中文标题自动转换为拼音（如 "数据分析" → "shu-ju-fen-xi"）
- 超长标题自动截断至 60 字符（在单词边界截断）
- 特殊字符会被 slugify 处理

**示例**：
- `1-python-shu-ju-fen-xi-ru-men`（标题：Python 数据分析入门）
- `2-hello-world-guide`（标题：Hello World Guide）

---

## 常见任务

### 添加新模板变量

1. 在 `RenderService._get_common_context()` 中添加变量
2. 在模板中使用 `{{ variable_name }}`
3. 更新 `docs/detailed-guide.md` 中的文档

### 修改主题样式

1. 编辑 `templates/PaperMint/static/css/papermint.css`
2. 运行 `tests/test_template_integrity.py` 确保一致性
3. 本地验证：`uv run python -m http.server 8000`

### 添加新页面类型

1. 在 `RenderService` 中添加渲染方法
2. 创建对应的模板文件
3. 在 `BlogGenerator.generate()` 中添加调用
4. 编写测试

---

## 开发规范

### Git 工作流

- **小步提交**：方便回滚和审查
- **避免频繁 `git commit --amend`**
- **改动前查看历史**：`git log --oneline -- 文件`
- **对比原始版本**：`git diff HEAD~n -- 文件`

### 路径处理

- 使用 `config.yaml` 配置路径，不硬编码
- 相对路径优先
- **避免 `Path.resolve()`**：可能破坏 GitHub Actions 中的路径逻辑

### 模板/CSS 改动

- 修改前检查 `templates/PaperMint/static/css/papermint.css` 现有样式
- 保持与 `.tag`, `.post` 等类名一致
- 不确定设计意图时先询问
- 本地验证后再提交

---

## 经验教训

### 2026-03-31 URL Slug 重构

**问题**：改 `{number}-{tag}` 为 `{number}-{title}` 时出现多个问题。

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

**改进措施**：
- `.claude/skills/my-coding-guidelines/SKILL.md` - TDD 检查清单
- `tests/test_template_integrity.py` - 模板完整性测试
- `.github/pull_request_template.md` - PR 强制检查清单

---

## 参考资源

- **详细指南**: `docs/detailed-guide.md`
- **TDD Skill**: `.claude/skills/my-coding-guidelines/SKILL.md`
- **PR 模板**: `.github/pull_request_template.md`
- **README**: `README.md`

---

## 快速参考卡

```bash
# 开发循环
uv run pytest -v                    # 1. 确保测试通过
# 修改代码
uv run pytest -v                    # 2. 验证修改
uv run ruff check . && uv run ty    # 3. 代码检查
uv run python -m http.server 8000   # 4. 本地验证

# 常见调试
uv run blog-gen <TOKEN> <REPO> 2>&1 | jq .  # 查看结构化日志
```
