# 项目实施方案：SEO 增强与架构优化 (plan.md)

## 一、 核心目标
本项目旨在提升个人博客的搜索引擎可见度（SEO）并优化代码结构。主要包含：
1. **语义化 URL (Slug)**：从文章标题提取拼音或英文作为文件名。
2. **SEO 模板化**：将 `sitemap.xml` 和 `robots.txt` 的内容从代码中剥离，使用模板管理。
3. **环境管理**：全面使用 `uv` 管理 Python 环境。

---

## 二、 模块设计

### 1. Slug 生成模块 (Slug Optimization)
- **实现逻辑**：
  - 自动识别标题内容。
  - **中文**：转换为拼音（全小写，连字符连接）。
  - **英文/数字**：保留原词（全小写）。
  - **特殊符号**：自动过滤或替换为连字符。
- **依赖库**：`pypinyin`, `python-slugify`。

### 2. SEO 模板化模块 (SEO Templatizing)
- **目录结构**：在 `templates/` 下创建独立的 SEO 模板。
  - `templates/seo/sitemap.xml`
  - `templates/seo/robots.txt`
- **实现方式**：使用 Jinja2 渲染模板，将动态数据（如文章列表、根路径）注入其中。

---

## 三、 实施步骤 (Execution)

### 第一步：环境配置
- 使用 `uv` 初始化环境。
- 安装依赖：`uv add pypinyin python-slugify jinja2`。

### 第二步：模板准备
- 创建 `templates/seo/` 文件夹。
- 编写 `sitemap.xml` 模板，遵循 Google 最佳实践（保留 `<loc>` 和 `<lastmod>`）。
- 编写 `robots.txt` 模板，支持从配置中读取 Sitemap 路径。

### 第三步：核心逻辑重构
- 在 `main.py` 中引入 Slug 生成逻辑。
- 修改 `save_articles_to_content_dir`，使文件名使用 Slug 而非 Issue 编号。
- 修改 `gen_sitemap` 和 `gen_robots_txt`，改为调用 Jinja2 渲染模板。

### 第四步：验证与清理
- 验证生成的文章链接是否符合预期。
- 验证 `sitemap.xml` 的路径是否与实际文件匹配。

---

## 四、 验收标准
1. 文章 URL 示例：`https://geoqiao.github.io/contents/blog/python-env-setup.html`。
2. `main.py` 中不再包含 `sitemap.xml` 和 `robots.txt` 的具体文本内容。
3. 所有依赖均通过 `uv` 管理。
