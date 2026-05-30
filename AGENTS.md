# AGENTS.md

AI coding agents 的工作指南（中文为主）。

## 项目概览

`escaping` 是一个基于 Python 的静态博客生成器，将 GitHub Issues 作为 CMS（内容管理系统）。

**核心特性：**

- 📝 **以 Issue 为博文**：直接在 GitHub Issues 中写作，支持标签分类
- 🤖 **全自动化流**：Issue 编辑/评论触发 GitHub Actions 自动构建
- 🎨 **双主题**：Escape1（亮色/暗色切换）和 Escape2（暗色终端风格）
- 🔍 **SEO 友好**：自动生成 sitemap.xml、robots.txt、Atom RSS
- 🌐 **中文优化**：中文标题自动转拼音生成 URL slug
- ⚡ **高性能**：基于 Python 3.9+ 和 uv 构建

**在线示例：** https://geoqiao.github.io/

---

## 技术栈

| 组件       | 技术                | 用途               |
| ---------- | ------------------- | ------------------ |
| 编程语言   | Python >=3.9        | 核心运行时         |
| 包管理     | uv                  | 依赖管理、虚拟环境 |
| GitHub API | PyGithub            | 获取 Issues 数据   |
| Markdown   | Marko (GFM + pangu) | Markdown 渲染      |
| 类型检查   | ty                  | 静态类型检查       |
| 模板引擎   | Jinja2              | HTML 模板渲染      |
| 配置管理   | pydantic-settings   | YAML 配置解析      |
| RSS 生成   | feedgen             | Atom 订阅生成      |
| 日志       | structlog           | 结构化日志         |
| 重试机制   | tenacity            | API 调用重试       |
| 中文转拼音 | pypinyin            | URL slug 生成      |

---

## 项目结构

```
escaping/
├── src/github_blog/           # 主源代码
│   ├── __init__.py
│   ├── cli.py                 # CLI 入口，BlogGenerator 主类
│   ├── config.py              # Pydantic 配置模型（8个配置section）
│   ├── models/                # 数据模型（预留）
│   ├── services/
│   │   ├── github_service.py  # GitHub API 封装（含重试逻辑）
│   │   └── render_service.py  # 模板渲染、RSS、站点地图
│   └── utils/
│       └── slug.py            # URL slug 生成（标题转拼音）
├── templates/
│   ├── Escape1/               # 亮色/暗色主题（classic minimal）
│   │   ├── base.html, home.html, index.html, post.html
│   │   ├── tag.html, tags.html, about.html
│   │   └── static/css/style.css, static/js/, static/images/
│   ├── Escape2/               # 暗色终端风格（nord配色）
│   │   ├── (same structure as Escape1)
│   │   └── static/css/style.css, static/js/, static/images/
│   └── seo/                   # SEO 模板（sitemap.xml.j2, robots.txt.j2）
├── tests/                     # 测试文件
│   ├── test_cli.py            # CLI 集成测试
│   ├── test_config.py         # 配置测试
│   ├── test_github_service.py # GitHub API 测试
│   ├── test_pagination.py     # 分页逻辑测试
│   ├── test_renderer.py       # 渲染服务测试
│   ├── test_slug.py           # URL slug 生成测试
│   └── test_template_integrity.py  # 模板完整性测试（Escape1 + Escape2）
├── config.yaml                # 博客配置
├── pyproject.toml             # 项目配置、依赖、工具设置
└── .github/workflows/
    ├── gen_site.yml           # 生成并部署站点
    ├── trigger.yml            # 监听 Issues 事件，触发 escaping
    └── sync.yml               # 同步 trigger.yml 到目标仓库
```

---

## 核心命令

### 环境设置

```bash
uv sync                # 安装依赖
source .venv/bin/activate  # 激活虚拟环境（可选）
```

### 本地开发

```bash
# 本地生成博客（需要 GitHub Token）
export G_T=ghp_xxx
uv run blog-gen

# 指定仓库（覆盖 config.yaml）
uv run blog-gen --repo user/repo

# 本地预览（必须从项目根目录启动）
uv run python -m http.server 8000
# 访问 http://localhost:8000
```

⚠️ **重要**：必须从项目根目录启动服务器，不要从 `output/` 启动。静态资源在 `output/templates/{theme}/` 下。

### 测试

```bash
uv run pytest -v                          # 运行所有测试
uv run pytest tests/test_config.py -v     # 运行特定测试文件
uv run pytest --cov=src --cov-report=term-missing  # 带覆盖率
```

### 代码质量检查

```bash
uv run ruff check .      # 代码检查（lint）
uv run ruff check --fix .  # 自动修复
uv run ruff format .     # 格式化代码
uv run ty                # 类型检查
```

---

## 配置说明

`config.yaml` 结构：

```yaml
github:
  repo: user/user.github.io # Issues 仓库
  username: user # GitHub 用户名

blog:
  title: "Blog Title"
  url: https://example.com
  author: "Author Name"
  description: "Description"

paths:
  output: output # 输出目录
  theme: Escape1 # 主题：Escape1 或 Escape2
  blog: blog # 文章子目录
  tag: tag # 标签子目录
  rss: atom.xml # RSS 文件名
  about: about.html
  page_size: 10 # 每页文章数
  home_post_count: 10
  language: zh-CN

about:
  avatar: https://github.com/user.png
  bio: "个人简介"
  expertise: ["技能1", "技能2"]
  links:
    - name: GitHub
      url: https://github.com/user

comments:
  provider: utterances # 评论 provider
  repo: "" # 评论仓库（留空则用 github.repo）
  theme: github-light
  theme_mode: auto # "auto" 跟随博客主题

security:
  token_env: G_T # Token 环境变量名
```

---

## TDD 开发流程（必须遵守）

**任何功能改动前，必须先写测试！**

```
写测试 → 运行失败 → 写代码 → 运行通过 → 重构
```

### 测试类型选择

| 改动类型 | 测试文件                           | 测试重点                   |
| -------- | ---------------------------------- | -------------------------- |
| 新增功能 | `tests/test_*.py`                  | 单元测试，验证具体功能     |
| 修改模板 | `tests/test_template_integrity.py` | 模板渲染正确性、文件存在性 |
| 修复 Bug | 对应模块的测试文件                 | 先写复现测试，再修复       |
| 重构代码 | `tests/test_cli.py`                | 集成测试，确保流程完整     |

---

## 代码风格规范

- **双引号** 字符串（Ruff 强制）
- **4 空格** 缩进
- **行长限制禁用**（`E501` 规则忽略）
- 使用**类型注解**
- 使用 **structlog** 进行结构化日志

### Ruff 配置

```toml
[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP", "B", "A", "C4", "SIM", "S", "RUF"]
ignore = ["E501"]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101"]
```

### 模板/CSS 规范

- 检查现有样式：`grep "class=" templates/Escape1/*.html`
- 保持与 `.tag`, `.post`, `.post-title` 等类一致
- 使用 `{{ theme_path }}` 变量引用主题路径
- 主题 CSS 文件：`templates/{Escape1,Escape2}/static/css/style.css`

---

## 安全考虑

1. **Token 安全**：GitHub Token 通过 `G_T` 环境变量注入，禁止硬编码
2. **输入验证**：使用 Pydantic 模型验证所有配置
3. **XSS 防护**：Jinja2 模板启用 `autoescape=True`，RSS 内容使用 CDATA
4. **依赖安全**：Ruff `S`（bandit）规则检查安全问题

---

## 部署流程

### 完整架构

```
GitHub Issues → geoqiao.github.io (trigger.yml) → escaping (gen_site.yml) → geoqiao.github.io (main)
```

### GitHub Actions 工作流

1. **gen_site.yml**（在 escaping 仓库）：
   - 触发：Issue 创建/编辑、评论、push 到 main、手动触发
   - 构建：安装 uv → 运行 `uv run blog-gen` → 复制到 `_site` → 推送到目标仓库

2. **trigger.yml**（在 geoqiao.github.io 仓库）：
   - 触发：Issue 创建/编辑、评论
   - 发送 dispatch 到 escaping 仓库

3. **sync.yml**（在 escaping 仓库）：
   - 触发：push 修改 trigger.yml 时
   - 同步 trigger.yml 到目标仓库

---

## URL Slug 生成规则

格式：`{issue_number}-{slugified-title}`

- Issue number 保证 URL 稳定性和唯一性
- 中文标题自动转换为拼音（如 "数据分析" → "shu-ju-fen-xi"）
- 超长标题自动截断至 60 字符（在单词边界截断）

**示例**：

- `1-python-shu-ju-fen-xi-ru-men`（标题：Python 数据分析入门）
- `2-hello-world-guide`（标题：Hello World Guide）

**URL 结构**：`/{blog_dir}/{slug}.html` → 如 `/blog/1-python-shu-ju-fen-xi-ru-men.html`

---

## 常见任务

### 添加新模板变量

1. 在 `RenderService._get_common_context()` 中添加变量
2. 在模板中使用 `{{ variable_name }}`

### 修改主题样式

1. 编辑 `templates/{Escape1,Escape2}/static/css/style.css`
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

- 修改前检查现有样式
- 保持与 `.tag`, `.post` 等类名一致
- 不确定设计意图时先询问
- 本地验证后再提交

---

## 经验教训

### URL Slug 重构教训

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

---

## 参考资源

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

# 本地生成
export G_T=ghp_xxx && uv run blog-gen

# 调试
uv run blog-gen 2>&1 | tail -50     # 查看日志
```
