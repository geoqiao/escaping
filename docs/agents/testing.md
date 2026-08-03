# Lean Testing and Delivery

本项目使用 TDD，但测试的目标是快速、可信地支持上线，而不是追求理论完备、分支穷举或 100% coverage。

## 核心原则

1. **先定义最小上线闭环**：优先打通 `IssueSnapshot → ContentCompiler → SiteModel → RouteRegistry → Renderer → Artifact`。
2. **一个行为只有一个主要测试 owner**：下层负责规则矩阵，上层只保留一个真实 tracer，不跨层重复同一断言。
3. **测试用户可观察行为和安全边界**：不锁定 private helper、mock 调用形状或当前代码组织。
4. **先运行真实构建**：完整站点生成、链接、canonical、XML 和浏览器检查的价值高于继续增加机械单测。
5. **覆盖率仅作线索**：不以 100% coverage 为目标，不为覆盖罕见分支而增加测试。

## 默认测试预算

- 每个功能 Ticket 默认 **3–6 个逻辑测试函数**。
- 两个或多个主题必须使用参数化测试，禁止复制整套测试。
- 新增测试代码不应明显超过对应生产代码；超出时必须说明真实风险和收益。
- 测试套件应保持在数秒级，避免逐字段、逐异常、逐主题机械展开。
- 已经发生过的真实安全或数据损坏问题可以保留专门 regression test。

预算是约束思考的默认值，不是为了压行数删除必要的安全保障。

## 测试职责归属

| 行为 | 主要测试 owner |
| --- | --- |
| YAML envelope、size、safe loading | front matter parser |
| 内容选择和 Blog/Idea/About 规则 | ContentCompiler |
| HTML allowlist 与危险 URL | sanitizer |
| 全站路径、碰撞和 output mapping | RouteRegistry |
| 模板变量和评论兼容行为 | theme contract |
| 完整内容到静态文件 | SiteCompiler integration tracer |
| 构建失败保留旧产物 | output staging |
| GitHub API 对象隔离 | GitHub adapter |

上层测试可以证明组件已正确接线，但不得重复下层的完整输入矩阵。

## 默认不写的测试

除非对应真实历史 Bug 或明确公共契约，否则不写：

- dataclass/frozen/getter/default/`hasattr` 测试；
- private helper、源码字符串或 `inspect.getsource()` 测试；
- 精确 mock 调用次数、顺序和 logger 参数形状；
- 每个字段、异常、主题各自一个函数的机械展开；
- 同一规则在 parser、compiler、renderer、CLI 多层重复验证；
- 仅为了提高 coverage 的不可达或极低概率分支测试；
- mutation testing 能构造、但没有现实用户失败场景的阻塞性测试。

## 高价值最小集合

每个完整功能通常只需要：

1. 一个核心 contract 参数化测试；
2. 一个安全或失败边界测试；
3. 一个真实 end-to-end tracer；
4. 必要时一个历史 Bug regression。

站点级 tracer 应使用少量代表性 Blog、Idea 和 About snapshots，生成页面后验证：

- 必需文件存在；
- front matter 未进入正文；
- internal links 与 output paths 一致；
- canonical、Atom、sitemap 和 Open Graph 使用同一 origin/route；
- 两个主题可渲染；
- comments 绑定 Issue number。

## Review 成本约束

Code review 只把以下问题作为 blocker：

- 会造成数据丢失、目录误删或安全漏洞；
- 会生成不可访问、链接断裂或语义错误的页面；
- 违反已接受内容协议的主要行为；
- 会让常规构建或部署失败。

Reviewer 不应因为缺少理论 mutation coverage、低概率平台分支或实现细节测试而阻塞。建议增加测试时，优先增强现有场景，而不是新增测试函数。

## 开发批次

较深的改造按可运行批次推进，而不是让每张 Ticket 都维持可独立发布的兼容层：

1. 内容模型：Blog、Ideas、About、Projects；
2. 主题：theme lock、shell 和全部页面；
3. 全站整合：SiteModel、RouteRegistry、SEO、strict pipeline；
4. 上线验证：真实构建、浏览器 smoke、Pages Artifact。

线上 `main` 保持稳定时，feature branch 可以直接建设 strict 新架构；不为中间提交维护 legacy `.html` 双管线。合并前必须完成一次完整验证。

## 验证命令

```bash
uv run pytest -q
uv run ruff check src/escaping tests
uv run ruff format --check src/escaping tests
uv run ty check
uv run escpe
```

生成站点后还应检查代表性的 Home、Blog、Ideas、About、Projects、Tags、Atom、sitemap 和 robots；前端行为使用桌面与移动端 browser smoke 验证。