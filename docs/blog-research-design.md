# 博客标题优化与选题生成工具设计文档

**日期**: 2026-03-26
**目标**: 基于 autoresearch 模式，实现博客标题批量优化与新选题推荐
**模型**: kimi-code (Moonshot AI)

---

## 1. 目标

实现一个独立的 Python 脚本 `blog-research.py`，能够：

1. **批量分析现有文章标题**：从 GitHub Issues 获取所有文章，使用 LLM 评估标题质量
2. **生成优化建议**：为低分标题提供 2-3 个优化候选
3. **推荐新选题**：基于现有标签分布，识别内容缺口并生成新选题
4. **输出 Markdown 报告**：便于人工审阅和决策

---

## 2. 架构设计

### 2.1 组件结构

```
blog-research.py              # CLI 入口
├── services/
│   └── github_service.py     # 复用现有，获取 Issues
├── research/
│   ├── __init__.py
│   ├── title_evaluator.py    # LLM 评分核心
│   ├── topic_generator.py    # 选题生成
│   └── report_writer.py      # Markdown 报告输出
├── config.py                 # 新增 research 配置
└── reports/                  # 输出目录
    └── title-research-YYYYMMDD.md
```

### 2.2 数据流

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Config    │───▶│ GitHub API  │───▶│  Evaluate   │───▶│   Report    │
│   (YAML)    │    │  (Issues)   │    │   Titles    │    │  (Markdown) │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                              │
                                              ▼
                                       ┌─────────────┐
                                       │   Generate  │
                                       │    Topics   │
                                       └─────────────┘
```

---

## 3. 组件详细设计

### 3.1 blog-research.py（入口脚本）

**职责**：
- 解析命令行参数
- 加载配置
- 协调各组件执行
- 控制流程和错误处理

**接口**：
```python
def main():
    """CLI入口"""
    # 1. 加载配置
    # 2. 获取GitHub Issues
    # 3. 评估标题
    # 4. 生成选题
    # 5. 写入报告
    # 6. 可选：自动打开报告

def run_research(config: ResearchConfig) -> ResearchResult:
    """执行完整研究流程"""
```

**命令行接口**：
```bash
# 基础运行
uv run blog-research.py

# 指定输出目录
uv run blog-research.py --output ./my-reports

# 只分析，不生成选题
uv run blog-research.py --no-topics

# 指定评分阈值
uv run blog-research.py --threshold 80
```

---

### 3.2 research/title_evaluator.py

**职责**：
- 调用 kimi-code 评估单个标题
- 返回评分、反馈和优化建议

**核心数据结构**：
```python
@dataclass
class TitleEvaluation:
    issue_number: int
    original_title: str
    content_preview: str  # 前500字用于上下文
    score: int  # 0-100
    feedback: str  # 评分理由
    weaknesses: list[str]  # 问题点
    candidates: list[TitleCandidate]  # 优化候选

@dataclass
class TitleCandidate:
    title: str
    predicted_score: int
    improvements: str  # 改进了什么
```

**评估维度**（Prompt 设计）：

```markdown
你是一个专业的博客标题优化专家。请评估以下标题，并给出优化建议。

## 评估维度（各25分，共100分）

1. **吸引力** (Attractiveness)
   - 是否激发点击欲望？
   - 是否有情感触发或好奇心钩子？
   - 是否有具体数字、结果或承诺？

2. **SEO友好度** (SEO)
   - 核心关键词是否前置？
   - 是否包含搜索意图明确的关键词？
   - 标题长度是否合适（15-30字）？

3. **可读性** (Readability)
   - 是否简洁明了，无歧义？
   - 断句是否自然？
   - 目标读者是否能快速理解价值？

4. **准确性** (Accuracy)
   - 是否与文章内容高度匹配？
   - 是否存在标题党嫌疑？

## 输出格式

```json
{
  "score": 75,
  "feedback": "总体评价...",
  "weaknesses": ["问题1", "问题2"],
  "candidates": [
    {
      "title": "优化后的标题1",
      "predicted_score": 88,
      "improvements": "改进了..."
    }
  ]
}
```

## 待评估标题
标题: {title}
内容摘要: {content_preview}
标签: {tags}
```

---

### 3.3 research/topic_generator.py

**职责**：
- 分析现有标签分布
- 识别内容缺口
- 生成新选题建议

**核心数据结构**：
```python
@dataclass
class TopicRecommendation:
    topic: str  # 选题方向
    proposed_title: str  # 建议标题
    tags: list[str]  # 相关标签
    rationale: str  # 推荐理由
    target_audience: str  # 目标受众
    difficulty: str  # 写作难度: 低/中/高
```

**生成逻辑**：

```python
def generate_topics(issues: list[Issue], count: int = 5) -> list[TopicRecommendation]:
    """
    1. 统计标签频率分布
    2. 识别高频标签的内容缺口
    3. 调用 LLM 生成选题建议
    """
    tag_distribution = analyze_tags(issues)
    content_gaps = identify_gaps(tag_distribution, issues)

    # Prompt LLM 生成选题
    prompt = f"""
    基于以下博客标签分布，推荐 {count} 个新选题：

    现有标签分布:
    {tag_distribution}

    内容缺口分析:
    {content_gaps}

    请推荐与现有内容形成互补的选题，避免重复。
    """
    return call_llm(prompt)
```

**选题生成 Prompt**：

```markdown
你是一个内容策略专家。基于博主的现有内容分布，推荐有价值的新选题。

## 现有内容分析

标签分布:
{tag_distribution}

已有文章主题:
{existing_topics}

## 任务

推荐 {count} 个新选题，要求：
1. 与现有内容形成互补，不重复
2. 符合博主的技术背景（金融+Python）
3. 有一定搜索需求和实用价值
4. 博主有能力完成

## 输出格式

```json
{
  "recommendations": [
    {
      "topic": "选题方向",
      "proposed_title": "建议标题",
      "tags": ["标签1", "标签2"],
      "rationale": "推荐理由",
      "target_audience": "目标读者",
      "difficulty": "中"
    }
  ]
}
```
```

---

### 3.4 research/report_writer.py

**职责**：
- 将评估结果和选题建议格式化为 Markdown
- 写入指定目录

**报告结构**：

```markdown
# 博客标题研究报告 - {date}

## 概览

- **分析文章数**: {total}
- **平均得分**: {avg_score}/100
- **建议优化**: {need_improvement}篇
- **生成新选题**: {topic_count}个
- **评分模型**: kimi-code

---

## 详细评估结果

### 需要优化的标题

#### 1. #{issue_number} {original_title} ({score}分)

- **标签**: {tags}
- **问题**: {feedback}
- **具体弱点**:
  - {weakness1}
  - {weakness2}

**优化建议**:

| 候选标题 | 预估分数 | 改进点 |
|---------|---------|--------|
| {candidate1} | {score1} | {improvement1} |
| {candidate2} | {score2} | {improvement2} |

---

### 优秀标题（90分以上）

可作为参考模板：

| 文章 | 标题 | 得分 | 亮点 |
|-----|-----|-----|-----|
| #{n} | {title} | {score} | {highlight} |

---

## 新选题推荐

基于标签分布分析，建议增加以下内容：

### 1. {topic}

- **建议标题**: {proposed_title}
- **标签**: {tags}
- **目标受众**: {audience}
- **写作难度**: {difficulty}
- **理由**: {rationale}

---

## 标签分布分析

{visualization or table}

### 内容缺口

- {gap1}
- {gap2}

---

## 下一步行动建议

1. **优先优化**: 得分低于60的标题
2. **考虑选题**: 推荐的前3个新选题
3. **标签优化**: 统一标签命名规范
```

---

## 4. 配置设计

### 4.1 config.yaml 新增部分

```yaml
research:
  llm:
    provider: "moonshot"
    api_key_env: "MOONSHOT_API_KEY"
    base_url: "https://api.kimi.com/coding"
    temperature: 0.3  # 评估需要稳定输出
    max_tokens: 2000

  evaluation:
    criteria:
      attractiveness:
        weight: 25
        description: "吸引点击的能力"
      seo:
        weight: 25
        description: "搜索引擎优化"
      readability:
        weight: 25
        description: "可读性和简洁度"
      accuracy:
        weight: 25
        description: "与内容匹配度"
    min_score_threshold: 75  # 低于此分建议优化
    batch_size: 5  # 每批处理的issue数（控制API调用频率）

  generation:
    topic_count: 5  # 生成新选题数量
    max_content_length: 500  # 发送给LLM的内容摘要长度

  output:
    dir: "./reports"
    auto_open: true  # 生成后是否用系统默认程序打开
    filename_template: "title-research-{date}.md"
```

### 4.2 环境变量

```bash
# 必需
export MOONSHOT_API_KEY="your-api-key"

# 可选（如需代理）
export MOONSHOT_BASE_URL="https://custom-proxy.com/v1"
```

---

## 5. 错误处理

| 错误场景 | 处理方式 |
|---------|---------|
| API Key 未设置 | 清晰提示设置环境变量 |
| API 调用失败 | 重试3次，失败则跳过当前issue，记录错误 |
| API 限流 | 指数退避重试，间隔 1s, 2s, 4s |
| GitHub API 失败 | 使用现有 github_service 的错误处理 |
| 报告目录不存在 | 自动创建 |
| 报告文件已存在 | 添加时间戳后缀 |

---

## 6. 实现优先级

### Phase 1: MVP（最小可用）
- [ ] 基础配置加载
- [ ] GitHub Issues 获取
- [ ] 简单标题评估（单维度评分）
- [ ] Markdown 报告输出

### Phase 2: 完整功能
- [ ] 四维度详细评估
- [ ] 优化候选生成
- [ ] 选题推荐功能
- [ ] 标签分布分析

### Phase 3: 优化
- [ ] 批量处理优化（并发控制）
- [ ] 报告可视化（可选图表）
- [ ] 历史报告对比
- [ ] 配置热加载

---

## 7. 测试策略

| 测试类型 | 内容 |
|---------|------|
| 单元测试 | 各组件独立测试，Mock LLM 响应 |
| 集成测试 | 端到端运行，验证报告格式 |
| 错误测试 | API 失败、网络超时等异常场景 |
| 配置测试 | 各种配置组合的正确性 |

---

## 8. 参考

- **autoresearch 模式**: https://github.com/karpathy/autoresearch
- **kimi-code 文档**: https://platform.moonshot.cn/docs
- **现有代码**: `src/escaping/services/github_service.py`

---

## 附录：Prompt 工程最佳实践

1. **明确输出格式**: 强制 JSON 输出，便于解析
2. **示例驱动**: 在 prompt 中提供优秀/差标题示例
3. **约束明确**: 字数、风格、受众等限制清晰
4. **迭代优化**: 先用5-10个标题测试 prompt 效果
5. **版本管理**: prompt 变更记录，便于回滚
