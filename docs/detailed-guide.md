# escaping 详细指南

> 本文档包含 AGENTS.md 中精简掉的详细内容。

---

## URL Slug 生成规则

格式：`{issue_number}-{slugified-title}`

- Issue number 保证 URL 稳定性和唯一性
- Title 转换为拼音 slug，保证可读性和 SEO 友好
- 超长标题自动截断至 60 字符（在单词边界截断）

示例：
- `1-python-shu-ju-fen-xi-ru-men`（标题：Python 数据分析入门）
- `2-hello-world-guide`（标题：Hello World Guide）
- `10-ji-qi-xue-xi-ru-men`（标题：机器学习入门）

**变更历史**：早期版本使用 tags 生成 slug，因标签变化会导致 URL 变化，现已改为使用 title。

---

## 架构详情

### 数据流

1. `BlogGenerator.generate()` 从 GitHub 获取 Issues（按创建者筛选）
2. 为每个 Issue 生成 slug（中文标题转换为拼音）
3. 使用 Marko 渲染 Markdown 为 HTML（图片添加 `loading="lazy"`）
4. 输出：
   - 独立文章页（`contents/blog/{slug}.html`）
   - 分页索引页（`contents/index.html`, `contents/page/{n}.html`）
   - 标签页（`contents/tag/{tag}.html`, `contents/tag/index.html`）
   - 主页（`index.html`）
   - RSS/Atom 订阅（`contents/atom.xml`）
   - 站点地图（`sitemap.xml`）
   - robots.txt

### 图片懒加载

`LazyImageRenderer` 类继承自 Marko 的 `HTMLRenderer`，通过正则注入 `loading="lazy"` 属性：

```python
return re.sub(r"<img\b", '<img loading="lazy"', result, count=1)
```

---

## 安全考虑

1. **Token 安全**: GitHub Token 通过 GitHub Secrets 注入，不要在代码中硬编码
2. **输入验证**: 使用 Pydantic 模型验证所有配置
3. **XSS 防护**: 
   - Jinja2 模板启用 `autoescape=True`
   - RSS 内容使用 CDATA 包装
4. **依赖安全**: 启用 Ruff 的 `S`（bandit）规则检查安全问题

---

## 常见任务

### 添加新模板变量

1. 在 `RenderService._get_common_context()` 中添加变量
2. 更新 `templates/PaperMint/README.md` 中的变量文档

### 修改主题

1. 编辑 `templates/PaperMint/` 下的模板文件
2. 静态资源放在 `templates/PaperMint/static/`
3. 使用 `{{ theme_path }}` 变量引用主题路径

### 添加新页面类型

1. 在 `RenderService` 中添加渲染方法
2. 创建对应的模板文件
3. 在 `BlogGenerator.generate()` 中添加调用

### 调试本地构建

```bash
# 使用 structlog 查看详细日志
uv run blog-gen <TOKEN> <REPO> 2>&1 | jq .
```

---

## Notes

- 生成的文件（`contents/`、`index.html`、`sitemap.xml`、`robots.txt`）已添加到 `.gitignore`，它们在 CI 中重新生成
- 博客只获取认证用户创建的 Issues（通过 `creator=me` 筛选）
- 项目使用 `uv` 而非 pip 进行包管理
- 开发时注意保持注释和文档的中文一致性
