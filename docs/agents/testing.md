# Lean Testing and Delivery

本项目使用 TDD，但测试的目标是快速、可信地支持上线，而不是追求理论完备、分支穷举或 100% coverage。

## 核心原则

1. **先定义最小上线闭环**：优先打通 `IssueSnapshot → compile_issues → ContentExporter → 导出目录`。
2. **一个行为只有一个主要测试 owner**：下层负责规则矩阵，上层只保留一个真实 tracer，不跨层重复同一断言。
3. **测试用户可观察行为和安全边界**：不锁定 private helper、mock 调用形状或当前代码组织。
4. **先运行真实导出**：用真实站点的 Issue 导出并与上一版逐字节比较，价值高于继续增加机械单测。
5. **覆盖率仅作线索**：不以 100% coverage 为目标，不为覆盖罕见分支而增加测试。

## 默认测试预算

- 每个功能 Ticket 默认 **3–6 个逻辑测试函数**：一个核心 contract 参数化测试、一个安全或失败边界、一个真实 end-to-end tracer，必要时一个真实历史 Bug 的 regression。
- 新增测试代码不应明显超过对应生产代码；超出时必须说明真实风险和收益。
- 重构测试本身无需先制造失败，但要先记录通过基线。

预算是约束思考的默认值，不是为了压行数删除必要的安全保障。

## 测试职责归属

| 行为 | 主要测试 owner |
| --- | --- |
| YAML envelope、size、safe loading | front matter parser（`test_frontmatter.py`） |
| 内容选择、Blog/Idea/About 规则、坏 Issue 跳过 | 内容内核（`test_issue_compilation.py`；`update_date` 见 `test_issue_content.py`） |
| HTML allowlist 与危险 URL | sanitizer（`test_html_sanitizer.py`） |
| Config 三段、其余段不读、错误信息 | Config（`test_config.py`） |
| 本地草稿检查 | Local Draft（`test_local_draft.py`） |
| 导出的 Markdown、manifest、导出目录、逐字节确定 | Content Export（`test_content_export.py`） |
| 导出失败保留旧文件、目录归属标记、路径范围 | output staging / safety（`test_output_staging.py`、`test_output_safety.py`） |
| GitHub API 对象隔离、重试、`--issues-json` 读取 | GitHub adapter（`test_issue_ingestion.py`） |
| 命令、退出码、Actions 注解/summary/outputs、Token 不外泄 | CLI（`test_cli.py`） |
| 发布到 PyPI 的 workflow | delivery（`test_delivery.py`） |
| wheel 内容与安装后的 `escaping-site` | package consumer（`test_package_consumer.py`：从 git 文件快照构建 wheel） |
| locked 源码安装与失败前提 | source consumer（`test_source_consumer.py`） |

上层测试可以证明组件已正确接线，但不得重复下层的完整输入矩阵。
渲染、网址、feed 和浏览器行为不在本仓库：它们的测试属于站点，默认主题的测试在模板仓库。

## 默认不写的测试

除非对应真实历史 Bug 或明确公共契约，否则不写：

- dataclass/frozen/getter/default/`hasattr` 测试；
- private helper、源码字符串或 `inspect.getsource()` 测试；
- 精确 mock 调用次数、顺序和 logger 参数形状；
- 每个字段、异常各自一个函数的机械展开；
- 同一规则在 parser、内核、导出、CLI 多层重复验证；
- 仅为了提高 coverage 的不可达或极低概率分支测试；
- mutation testing 能构造、但没有现实用户失败场景的阻塞性测试。

## Review 成本约束

Code review 只把以下问题作为 blocker：

- 会造成数据丢失、目录误删或安全漏洞；
- 会导出错误的内容、丢失已发布内容或违反 Content Export 契约；
- 违反已接受内容协议的主要行为；
- 会让常规导出失败。

Reviewer 不应因为缺少理论 mutation coverage、低概率平台分支或实现细节测试而阻塞。建议增加测试时，优先增强现有场景，而不是新增测试函数。

## 验证命令

[CI workflow](../../.github/workflows/ci.yml) 是自动检查的执行来源，以下命令用于本地复现。

### 环境准备

使用 Python 3.14.x 和 uv 0.12.20：

```bash
uv sync --locked
```

### 局部验证

按改动选择相关 owner，例如内容规则：

```bash
uv run pytest -q tests/test_issue_compilation.py
```

改动打包配置或发布 workflow 时运行：

```bash
uv run pytest -q tests/test_delivery.py tests/test_package_consumer.py tests/test_source_consumer.py
```

这些测试会调用本机 `uv` 和 `git`。wheel 用例从 `git ls-files` 列出的文件快照构建
（见 `tests/conftest.py` 的 `source_snapshot`），被忽略的 `build/`、`*.egg-info` 不会混入；
新文件需未被 `.gitignore` 忽略才会进入快照。

纯文档改动检查本地链接及锚点、示例路径、配置与命令；不要求为了文档措辞制造失败单测。
若文档更正涉及公共行为，运行该行为已有的 owner 测试，不能仅凭改文档宣称实现符合契约。

### 完整验证

合并前运行一次完整验证：

```bash
uv lock --check
CI=true uv run pytest -q -ra
uv run ruff check src/escaping_site tests
uv run ruff format --check src/escaping_site tests
uv run ty check src/escaping_site tests
git diff --check
```

记录实际解释器、输入版本、通过数和跳过项。不要把局部通过报告成完整验证。

改动内容规则或导出格式时，另用一个真实站点的 Issue 导出，并与改动前的导出做 `diff -r`：

```bash
gh api --paginate --slurp 'repos/OWNER/REPO/issues?state=all&per_page=100' > /tmp/issues.json
uv run escaping-site export --config /path/to/site/config.yaml --issues-json /tmp/issues.json
```
