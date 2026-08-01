# 博客标题优化工具 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现基于 Kimi API 的博客标题批量评估与新选题推荐工具

**Architecture:** 独立 CLI 脚本 `blog-research.py`，复用现有 GitHub Service 获取 Issues，通过研究模块（title_evaluator, topic_generator, report_writer）完成评估和报告生成，输出 Markdown 报告到 `reports/` 目录。

**Tech Stack:** Python 3.11+, Pydantic Settings, OpenAI SDK (兼容 Moonshot API), pytest

---

## File Structure

```
src/escaping/
├── cli.py                      # 现有，保持不变
├── config.py                   # 修改：添加 ResearchConfig
├── services/
│   ├── github_service.py       # 现有，复用
│   ├── render_service.py       # 现有
│   └── __init__.py
└── research/                   # 新建目录
    ├── __init__.py
    ├── title_evaluator.py      # LLM 评分核心
    ├── topic_generator.py      # 选题生成
    └── report_writer.py        # Markdown 报告输出

blog-research.py                # 新建：CLI 入口脚本（项目根目录）

tests/research/                 # 新建目录
├── __init__.py
├── test_title_evaluator.py     # 测试：标题评估
├── test_topic_generator.py     # 测试：选题生成
└── test_report_writer.py       # 测试：报告生成

reports/                        # 新建目录（gitignore）
```

---

## Task 1: 配置模块扩展

**Files:**
- Modify: `src/escaping/config.py`

**目标:** 添加 ResearchConfig 配置类，支持 Kimi API 配置

- [ ] **Step 1: 编写 ResearchConfig 模型测试**

Create: `tests/test_config_research.py`

```python
import os
from unittest.mock import patch

import pytest
from pydantic_settings import SettingsConfigDict

from src.escaping.config import ResearchConfig


def test_research_config_default():
    """测试 ResearchConfig 默认值"""
    with patch.dict(os.environ, {"MOONSHOT_API_KEY": "test-key"}):
        config = ResearchConfig()
        assert config.provider == "moonshot"
        assert config.base_url == "https://api.kimi.com/coding"
        assert config.temperature == 0.3
        assert config.max_tokens == 2000
        assert config.min_score_threshold == 75
        assert config.topic_count == 5


def test_research_config_from_env():
    """测试从环境变量读取 API Key"""
    with patch.dict(os.environ, {"MOONSHOT_API_KEY": "secret-key"}):
        config = ResearchConfig()
        assert config.api_key == "secret-key"


def test_research_config_missing_api_key():
    """测试缺少 API Key 时抛出错误"""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="MOONSHOT_API_KEY"):
            ResearchConfig()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_config_research.py -v`
Expected: FAIL with "ResearchConfig not defined"

- [ ] **Step 3: 在 config.py 中添加 ResearchConfig**

Modify: `src/escaping/config.py`

```python
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ResearchConfig(BaseSettings):
    """博客研究工具配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM 配置
    provider: str = Field(default="moonshot", description="LLM提供商")
    api_key: str = Field(
        default_factory=lambda: os.getenv("MOONSHOT_API_KEY", ""),
        description="API密钥",
    )
    base_url: str = Field(
        default="https://api.kimi.com/coding",
        description="API基础URL",
    )
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, ge=100, le=8000)

    # 评估配置
    min_score_threshold: int = Field(default=75, ge=0, le=100)
    batch_size: int = Field(default=5, ge=1, le=20)

    # 生成配置
    topic_count: int = Field(default=5, ge=1, le=20)
    max_content_length: int = Field(default=500, ge=100, le=2000)

    # 输出配置
    output_dir: str = Field(default="./reports")
    auto_open: bool = Field(default=False)

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v:
            raise ValueError("MOONSHOT_API_KEY environment variable is required")
        return v

    def get_llm_client_kwargs(self) -> dict:
        """获取 LLM 客户端初始化参数"""
        return {
            "api_key": self.api_key,
            "base_url": self.base_url,
        }
```

同时更新文件顶部的导入，确保 `os` 已导入。

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_config_research.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_config_research.py src/escaping/config.py
git commit -m "feat: add ResearchConfig for blog research tool"
```

---

## Task 2: Title Evaluator 核心模块

**Files:**
- Create: `src/escaping/research/__init__.py`
- Create: `src/escaping/research/title_evaluator.py`
- Create: `tests/research/__init__.py`
- Create: `tests/research/test_title_evaluator.py`

**目标:** 实现基于 LLM 的标题评估器

- [ ] **Step 1: 编写 TitleEvaluator 测试**

Create: `tests/research/test_title_evaluator.py`

```python
import json
from unittest.mock import Mock, patch

import pytest

from src.escaping.research.title_evaluator import (
    TitleCandidate,
    TitleEvaluation,
    TitleEvaluator,
)


def test_title_evaluation_dataclass():
    """测试 TitleEvaluation 数据类"""
    candidate = TitleCandidate(
        title="优化后的标题",
        predicted_score=85,
        improvements="更吸引人"
    )
    evaluation = TitleEvaluation(
        issue_number=1,
        original_title="原标题",
        content_preview="内容摘要",
        score=65,
        feedback="需要改进",
        weaknesses=["太平淡"],
        candidates=[candidate]
    )
    assert evaluation.score == 65
    assert len(evaluation.candidates) == 1


def test_title_evaluator_init():
    """测试初始化"""
    config = Mock()
    config.api_key = "test-key"
    config.base_url = "https://api.test.com"
    config.temperature = 0.3
    config.max_tokens = 2000

    evaluator = TitleEvaluator(config)
    assert evaluator.config == config


@patch("src.escaping.research.title_evaluator.OpenAI")
def test_evaluate_success(mock_openai_class):
    """测试评估成功"""
    # 模拟 LLM 响应
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = json.dumps({
        "score": 75,
        "feedback": "总体不错",
        "weaknesses": ["关键词后置"],
        "candidates": [
            {
                "title": "优化标题1",
                "predicted_score": 85,
                "improvements": "关键词前置"
            }
        ]
    })

    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai_class.return_value = mock_client

    config = Mock()
    config.api_key = "test-key"
    config.base_url = "https://api.test.com"
    config.temperature = 0.3
    config.max_tokens = 2000

    evaluator = TitleEvaluator(config)
    result = evaluator.evaluate(
        issue_number=1,
        title="测试标题",
        content="测试内容",
        tags=["python"]
    )

    assert result.score == 75
    assert result.issue_number == 1
    assert len(result.candidates) == 1
    assert result.candidates[0].predicted_score == 85


@patch("src.escaping.research.title_evaluator.OpenAI")
def test_evaluate_api_error(mock_openai_class):
    """测试 API 错误处理"""
    mock_client = Mock()
    mock_client.chat.completions.create.side_effect = Exception("API Error")
    mock_openai_class.return_value = mock_client

    config = Mock()
    config.api_key = "test-key"
    config.base_url = "https://api.test.com"
    config.temperature = 0.3
    config.max_tokens = 2000

    evaluator = TitleEvaluator(config)
    result = evaluator.evaluate(
        issue_number=1,
        title="测试标题",
        content="测试内容",
        tags=["python"]
    )

    # 错误时返回默认评分
    assert result.score == 50
    assert "评估失败" in result.feedback
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/research/test_title_evaluator.py -v`
Expected: FAIL with "Module not found"

- [ ] **Step 3: 创建 TitleEvaluator 模块**

Create: `src/escaping/research/__init__.py`

```python
"""博客研究工具模块"""

from src.escaping.research.title_evaluator import TitleEvaluator
from src.escaping.research.topic_generator import TopicGenerator
from src.escaping.research.report_writer import ReportWriter

__all__ = ["TitleEvaluator", "TopicGenerator", "ReportWriter"]
```

Create: `src/escaping/research/title_evaluator.py`

```python
"""标题评估器 - 使用 LLM 评估博客标题质量"""

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from openai import OpenAI

if TYPE_CHECKING:
    from src.escaping.config import ResearchConfig

logger = logging.getLogger(__name__)


@dataclass
class TitleCandidate:
    """优化后的标题候选"""
    title: str
    predicted_score: int
    improvements: str


@dataclass
class TitleEvaluation:
    """标题评估结果"""
    issue_number: int
    original_title: str
    content_preview: str
    score: int
    feedback: str
    weaknesses: list[str]
    candidates: list[TitleCandidate]


class TitleEvaluator:
    """标题评估器"""

    def __init__(self, config: "ResearchConfig"):
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    def _build_prompt(self, title: str, content: str, tags: list[str]) -> str:
        """构建评估 prompt"""
        content_preview = content[:self.config.max_content_length] if content else ""
        tags_str = ", ".join(tags) if tags else "无"

        return f"""你是一个专业的博客标题优化专家。请评估以下标题，并给出优化建议。

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
{{
  "score": 75,
  "feedback": "总体评价...",
  "weaknesses": ["问题1", "问题2"],
  "candidates": [
    {{
      "title": "优化后的标题1",
      "predicted_score": 88,
      "improvements": "改进了..."
    }}
  ]
}}
```

## 待评估标题

标题: {title}
内容摘要: {content_preview}
标签: {tags_str}"""

    def evaluate(
        self,
        issue_number: int,
        title: str,
        content: str,
        tags: list[str]
    ) -> TitleEvaluation:
        """评估单个标题"""
        prompt = self._build_prompt(title, content, tags)

        try:
            response = self.client.chat.completions.create(
                model="",  # Kimi API 不需要指定 model
                messages=[
                    {"role": "system", "content": "你是一个专业的博客标题优化专家。只输出JSON格式。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

            content_text = response.choices[0].message.content
            # 提取 JSON（处理可能的 markdown 代码块）
            if "```json" in content_text:
                content_text = content_text.split("```json")[1].split("```")[0]
            elif "```" in content_text:
                content_text = content_text.split("```")[1].split("```")[0]

            result = json.loads(content_text.strip())

            candidates = [
                TitleCandidate(
                    title=c["title"],
                    predicted_score=c["predicted_score"],
                    improvements=c["improvements"]
                )
                for c in result.get("candidates", [])
            ]

            return TitleEvaluation(
                issue_number=issue_number,
                original_title=title,
                content_preview=content[:200],
                score=result.get("score", 50),
                feedback=result.get("feedback", "无反馈"),
                weaknesses=result.get("weaknesses", []),
                candidates=candidates
            )

        except Exception as e:
            logger.error(f"评估标题失败 (issue #{issue_number}): {e}")
            return TitleEvaluation(
                issue_number=issue_number,
                original_title=title,
                content_preview=content[:200] if content else "",
                score=50,
                feedback=f"评估失败: {str(e)}",
                weaknesses=["API调用失败"],
                candidates=[]
            )

    def evaluate_batch(
        self,
        issues: list[dict],
        progress_callback=None
    ) -> list[TitleEvaluation]:
        """批量评估标题"""
        results = []
        for i, issue in enumerate(issues):
            evaluation = self.evaluate(
                issue_number=issue.get("number", 0),
                title=issue.get("title", ""),
                content=issue.get("body", ""),
                tags=issue.get("labels", [])
            )
            results.append(evaluation)
            if progress_callback:
                progress_callback(i + 1, len(issues))
        return results
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/research/test_title_evaluator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/escaping/research/ tests/research/
git commit -m "feat: add TitleEvaluator with Kimi API integration"
```

---

## Task 3: Topic Generator 模块

**Files:**
- Create: `src/escaping/research/topic_generator.py`
- Create: `tests/research/test_topic_generator.py`

**目标:** 实现基于标签分布的选题推荐

- [ ] **Step 1: 编写 TopicGenerator 测试**

Create: `tests/research/test_topic_generator.py`

```python
from unittest.mock import Mock, patch

import pytest

from src.escaping.research.topic_generator import (
    TopicGenerator,
    TopicRecommendation,
)


def test_topic_recommendation_dataclass():
    """测试 TopicRecommendation 数据类"""
    recommendation = TopicRecommendation(
        topic="uv进阶",
        proposed_title="uv工作流：从入门到生产环境",
        tags=["python", "uv"],
        rationale="已有基础文章，缺进阶内容",
        target_audience="Python开发者",
        difficulty="中"
    )
    assert recommendation.topic == "uv进阶"
    assert recommendation.difficulty == "中"


def test_analyze_tags():
    """测试标签分析"""
    issues = [
        {"labels": ["python", "uv"]},
        {"labels": ["python", "vscode"]},
        {"labels": ["python"]},
    ]

    config = Mock()
    generator = TopicGenerator(config)
    distribution = generator._analyze_tags(issues)

    assert distribution["python"] == 3
    assert distribution["uv"] == 1
    assert distribution["vscode"] == 1


def test_analyze_tags_empty():
    """测试空标签处理"""
    issues = [
        {"labels": []},
        {"labels": None},
    ]

    config = Mock()
    generator = TopicGenerator(config)
    distribution = generator._analyze_tags(issues)

    assert distribution == {}


@patch("src.escaping.research.topic_generator.OpenAI")
def test_generate_topics(mock_openai_class):
    """测试选题生成"""
    # 模拟 LLM 响应
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = """```json
{
  "recommendations": [
    {
      "topic": "测试选题",
      "proposed_title": "测试标题",
      "tags": ["python"],
      "rationale": "测试理由",
      "target_audience": "开发者",
      "difficulty": "低"
    }
  ]
}
```"""

    mock_client = Mock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai_class.return_value = mock_client

    config = Mock()
    config.api_key = "test-key"
    config.base_url = "https://api.test.com"
    config.temperature = 0.3
    config.max_tokens = 2000
    config.topic_count = 1

    generator = TopicGenerator(config)
    issues = [
        {"title": "文章1", "labels": ["python"]},
    ]

    topics = generator.generate(issues)

    assert len(topics) == 1
    assert topics[0].topic == "测试选题"
    assert topics[0].difficulty == "低"


@patch("src.escaping.research.topic_generator.OpenAI")
def test_generate_topics_api_error(mock_openai_class):
    """测试 API 错误处理"""
    mock_client = Mock()
    mock_client.chat.completions.create.side_effect = Exception("API Error")
    mock_openai_class.return_value = mock_client

    config = Mock()
    config.api_key = "test-key"
    config.base_url = "https://api.test.com"
    config.temperature = 0.3
    config.max_tokens = 2000
    config.topic_count = 5

    generator = TopicGenerator(config)
    issues = [{"title": "文章1", "labels": ["python"]}]

    topics = generator.generate(issues)

    # 错误时返回空列表
    assert topics == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/research/test_topic_generator.py -v`
Expected: FAIL with "Module not found"

- [ ] **Step 3: 创建 TopicGenerator 模块**

Create: `src/escaping/research/topic_generator.py`

```python
"""选题生成器 - 基于标签分布推荐新选题"""

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING
from collections import Counter

from openai import OpenAI

if TYPE_CHECKING:
    from src.escaping.config import ResearchConfig

logger = logging.getLogger(__name__)


@dataclass
class TopicRecommendation:
    """选题推荐"""
    topic: str
    proposed_title: str
    tags: list[str]
    rationale: str
    target_audience: str
    difficulty: str  # 低/中/高


class TopicGenerator:
    """选题生成器"""

    def __init__(self, config: "ResearchConfig"):
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )

    def _analyze_tags(self, issues: list[dict]) -> dict[str, int]:
        """分析标签分布"""
        all_tags = []
        for issue in issues:
            labels = issue.get("labels", [])
            if labels:
                all_tags.extend(labels)
        return dict(Counter(all_tags).most_common())

    def _build_prompt(self, tag_distribution: dict, existing_topics: list[str]) -> str:
        """构建选题生成 prompt"""
        tags_str = "\n".join([f"- {tag}: {count}篇" for tag, count in tag_distribution.items()])
        topics_str = "\n".join([f"- {t}" for t in existing_topics[:20]])  # 限制数量

        return f"""你是一个内容策略专家。基于博主的现有内容分布，推荐有价值的新选题。

## 现有内容分析

标签分布:
{tags_str}

已有文章主题:
{topics_str}

## 任务

推荐 {self.config.topic_count} 个新选题，要求：
1. 与现有内容形成互补，不重复
2. 符合博主的技术背景（金融+Python）
3. 有一定搜索需求和实用价值
4. 博主有能力完成

## 输出格式

```json
{{
  "recommendations": [
    {{
      "topic": "选题方向",
      "proposed_title": "建议标题",
      "tags": ["标签1", "标签2"],
      "rationale": "推荐理由",
      "target_audience": "目标读者",
      "difficulty": "中"
    }}
  ]
}}
```"""

    def generate(self, issues: list[dict]) -> list[TopicRecommendation]:
        """生成选题建议"""
        tag_distribution = self._analyze_tags(issues)
        existing_topics = [i.get("title", "") for i in issues]

        if not tag_distribution:
            logger.warning("没有标签数据，无法生成选题")
            return []

        prompt = self._build_prompt(tag_distribution, existing_topics)

        try:
            response = self.client.chat.completions.create(
                model="",  # Kimi API 不需要指定 model
                messages=[
                    {"role": "system", "content": "你是一个专业的内容策略专家。只输出JSON格式。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

            content_text = response.choices[0].message.content
            # 提取 JSON
            if "```json" in content_text:
                content_text = content_text.split("```json")[1].split("```")[0]
            elif "```" in content_text:
                content_text = content_text.split("```")[1].split("```")[0]

            result = json.loads(content_text.strip())

            recommendations = [
                TopicRecommendation(
                    topic=r["topic"],
                    proposed_title=r["proposed_title"],
                    tags=r.get("tags", []),
                    rationale=r["rationale"],
                    target_audience=r["target_audience"],
                    difficulty=r["difficulty"]
                )
                for r in result.get("recommendations", [])
            ]

            return recommendations

        except Exception as e:
            logger.error(f"生成选题失败: {e}")
            return []
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/research/test_topic_generator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/escaping/research/topic_generator.py tests/research/test_topic_generator.py
git commit -m "feat: add TopicGenerator for content recommendations"
```

---

## Task 4: Report Writer 模块

**Files:**
- Create: `src/escaping/research/report_writer.py`
- Create: `tests/research/test_report_writer.py`

**目标:** 实现 Markdown 报告生成器

- [ ] **Step 1: 编写 ReportWriter 测试**

Create: `tests/research/test_report_writer.py`

```python
import os
import tempfile
from datetime import datetime

import pytest

from src.escaping.research.report_writer import ReportWriter
from src.escaping.research.title_evaluator import TitleEvaluation, TitleCandidate
from src.escaping.research.topic_generator import TopicRecommendation


def test_report_writer_init():
    """测试初始化"""
    config = {"output_dir": "/tmp/reports"}
    writer = ReportWriter(config)
    assert writer.output_dir == "/tmp/reports"


def test_write_report():
    """测试报告生成"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {"output_dir": tmpdir}
        writer = ReportWriter(config)

        # 准备测试数据
        evaluations = [
            TitleEvaluation(
                issue_number=1,
                original_title="原标题",
                content_preview="内容",
                score=65,
                feedback="需要改进",
                weaknesses=["太平淡"],
                candidates=[
                    TitleCandidate("优化标题", 85, "更吸引人")
                ]
            )
        ]

        topics = [
            TopicRecommendation(
                topic="新选题",
                proposed_title="建议标题",
                tags=["python"],
                rationale="理由",
                target_audience="开发者",
                difficulty="中"
            )
        ]

        tag_distribution = {"python": 5, "vscode": 2}

        # 生成报告
        filepath = writer.write(
            evaluations=evaluations,
            topics=topics,
            tag_distribution=tag_distribution
        )

        # 验证文件存在
        assert os.path.exists(filepath)

        # 验证内容
        with open(filepath) as f:
            content = f.read()
            assert "博客标题研究报告" in content
            assert "原标题" in content
            assert "新选题" in content
            assert "python" in content


def test_calculate_stats():
    """测试统计计算"""
    evaluations = [
        TitleEvaluation(1, "t1", "c", 80, "ok", [], []),
        TitleEvaluation(2, "t2", "c", 60, "bad", ["weak"], []),
        TitleEvaluation(3, "t3", "c", 90, "good", [], []),
    ]

    config = {"output_dir": "/tmp"}
    writer = ReportWriter(config)
    stats = writer._calculate_stats(evaluations, threshold=75)

    assert stats["total"] == 3
    assert stats["average_score"] == 76.7  # (80+60+90)/3
    assert stats["need_improvement"] == 1  # score < 75
    assert stats["excellent"] == 1  # score >= 90


def test_format_tag_distribution():
    """测试标签分布格式化"""
    config = {"output_dir": "/tmp"}
    writer = ReportWriter(config)

    distribution = {"python": 10, "vscode": 5, "sql": 2}
    formatted = writer._format_tag_distribution(distribution)

    assert "python" in formatted
    assert "10" in formatted
    assert "vscode" in formatted
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/research/test_report_writer.py -v`
Expected: FAIL with "Module not found"

- [ ] **Step 3: 创建 ReportWriter 模块**

Create: `src/escaping/research/report_writer.py`

```python
"""报告生成器 - 输出 Markdown 格式研究报告"""

import os
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.escaping.research.title_evaluator import TitleEvaluation
    from src.escaping.research.topic_generator import TopicRecommendation


class ReportWriter:
    """Markdown 报告生成器"""

    def __init__(self, config: dict):
        self.output_dir = config.get("output_dir", "./reports")
        self._ensure_output_dir()

    def _ensure_output_dir(self):
        """确保输出目录存在"""
        os.makedirs(self.output_dir, exist_ok=True)

    def _calculate_stats(
        self,
        evaluations: list["TitleEvaluation"],
        threshold: int = 75
    ) -> dict:
        """计算统计数据"""
        if not evaluations:
            return {
                "total": 0,
                "average_score": 0,
                "need_improvement": 0,
                "excellent": 0,
            }

        scores = [e.score for e in evaluations]
        return {
            "total": len(evaluations),
            "average_score": round(sum(scores) / len(scores), 1),
            "need_improvement": sum(1 for s in scores if s < threshold),
            "excellent": sum(1 for s in scores if s >= 90),
        }

    def _format_tag_distribution(self, distribution: dict[str, int]) -> str:
        """格式化标签分布为 Markdown 表格"""
        if not distribution:
            return "暂无标签数据"

        lines = ["| 标签 | 文章数 | 占比 |", "|-----|-------|-----|"]
        total = sum(distribution.values())
        for tag, count in sorted(distribution.items(), key=lambda x: x[1], reverse=True):
            percentage = round(count / total * 100, 1)
            lines.append(f"| {tag} | {count} | {percentage}% |")
        return "\n".join(lines)

    def _generate_evaluation_section(
        self,
        evaluations: list["TitleEvaluation"],
        threshold: int
    ) -> str:
        """生成标题评估部分"""
        lines = []

        # 需要优化的标题
        need_improvement = [e for e in evaluations if e.score < threshold]
        if need_improvement:
            lines.append("### 需要优化的标题\n")
            for eval in sorted(need_improvement, key=lambda x: x.score):
                lines.append(f"#### #{eval.issue_number} {eval.original_title} ({eval.score}分)\n")
                lines.append(f"- **内容摘要**: {eval.content_preview[:100]}...")
                lines.append(f"- **问题**: {eval.feedback}")
                if eval.weaknesses:
                    lines.append("- **具体弱点**:")
                    for w in eval.weaknesses:
                        lines.append(f"  - {w}")

                if eval.candidates:
                    lines.append("\n**优化建议**:\n")
                    lines.append("| 候选标题 | 预估分数 | 改进点 |")
                    lines.append("|---------|---------|--------|")
                    for c in eval.candidates[:3]:  # 最多显示3个
                        lines.append(f"| {c.title} | {c.predicted_score} | {c.improvements} |")
                lines.append("")

        # 优秀标题
        excellent = [e for e in evaluations if e.score >= 90]
        if excellent:
            lines.append("\n### 优秀标题（90分以上）\n")
            lines.append("可作为参考模板：\n")
            lines.append("| 文章 | 标题 | 得分 | 亮点 |")
            lines.append("|-----|-----|-----|-----|")
            for eval in sorted(excellent, key=lambda x: x.score, reverse=True):
                highlight = "、".join(eval.weaknesses) if eval.weaknesses else "各方面优秀"
                lines.append(f"| #{eval.issue_number} | {eval.original_title} | {eval.score} | {highlight} |")
            lines.append("")

        return "\n".join(lines)

    def _generate_topics_section(self, topics: list["TopicRecommendation"]) -> str:
        """生成选题推荐部分"""
        if not topics:
            return "暂无选题推荐。"

        lines = []
        for i, topic in enumerate(topics, 1):
            lines.append(f"### {i}. {topic.topic}\n")
            lines.append(f"- **建议标题**: {topic.proposed_title}")
            lines.append(f"- **标签**: {', '.join(topic.tags)}")
            lines.append(f"- **目标受众**: {topic.target_audience}")
            lines.append(f"- **写作难度**: {topic.difficulty}")
            lines.append(f"- **理由**: {topic.rationale}")
            lines.append("")

        return "\n".join(lines)

    def write(
        self,
        evaluations: list["TitleEvaluation"],
        topics: list["TopicRecommendation"],
        tag_distribution: dict[str, int],
        threshold: int = 75
    ) -> str:
        """生成并保存报告"""
        stats = self._calculate_stats(evaluations, threshold)
        date_str = datetime.now().strftime("%Y-%m-%d")

        content = f"""# 博客标题研究报告 - {date_str}

## 概览

- **分析文章数**: {stats["total"]}
- **平均得分**: {stats["average_score"]}/100
- **建议优化**: {stats["need_improvement"]}篇
- **优秀标题**: {stats["excellent"]}篇
- **生成新选题**: {len(topics)}个

---

## 详细评估结果

{self._generate_evaluation_section(evaluations, threshold)}

---

## 新选题推荐

基于标签分布分析，建议增加以下内容：

{self._generate_topics_section(topics)}

---

## 标签分布分析

{self._format_tag_distribution(tag_distribution)}

### 内容缺口分析

基于现有内容分布，以下方向可能值得补充：

1. **高频标签深化**: {list(tag_distribution.keys())[0] if tag_distribution else "N/A"} 类内容较多，可考虑进阶主题
2. **低频标签补充**: 关注标签较少的领域，形成差异化
3. **交叉领域**: 结合金融+Python的独特视角

---

## 下一步行动建议

1. **优先优化**: 得分低于{threshold}的标题，参考候选建议修改
2. **选题规划**: 从前3个推荐选题中选择1-2个列入写作计划
3. **标签规范**: 统一标签命名，避免类似标签分散（如"python"和"Python"）

---

*报告生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
*评估模型: Kimi API*
"""

        # 确定文件名
        filename = f"title-research-{date_str}.md"
        filepath = os.path.join(self.output_dir, filename)

        # 处理文件已存在的情况
        counter = 1
        while os.path.exists(filepath):
            filename = f"title-research-{date_str}-{counter}.md"
            filepath = os.path.join(self.output_dir, filename)
            counter += 1

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return filepath
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/research/test_report_writer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/escaping/research/report_writer.py tests/research/test_report_writer.py
git commit -m "feat: add ReportWriter for markdown report generation"
```

---

## Task 5: CLI 入口脚本

**Files:**
- Create: `blog-research.py` (项目根目录)
- Create: `tests/test_blog_research_cli.py`

**目标:** 实现主入口脚本，协调各模块

- [ ] **Step 1: 编写 CLI 测试**

Create: `tests/test_blog_research_cli.py`

```python
from unittest.mock import Mock, patch, MagicMock

import pytest


@patch("blog_research.ResearchConfig")
@patch("blog_research.GitHubService")
@patch("blog_research.TitleEvaluator")
@patch("blog_research.TopicGenerator")
@patch("blog_research.ReportWriter")
def test_main_success(
    mock_writer_class,
    mock_generator_class,
    mock_evaluator_class,
    mock_github_class,
    mock_config_class
):
    """测试主流程成功"""
    # 模拟配置
    mock_config = Mock()
    mock_config.api_key = "test-key"
    mock_config.output_dir = "/tmp/reports"
    mock_config.min_score_threshold = 75
    mock_config_class.return_value = mock_config

    # 模拟 GitHub 数据
    mock_github = Mock()
    mock_github.get_issues.return_value = [
        {"number": 1, "title": "测试", "body": "内容", "labels": ["python"]}
    ]
    mock_github_class.return_value = mock_github

    # 模拟评估结果
    mock_evaluator = Mock()
    mock_evaluator.evaluate_batch.return_value = []
    mock_evaluator_class.return_value = mock_evaluator

    # 模拟选题结果
    mock_generator = Mock()
    mock_generator.generate.return_value = []
    mock_generator_class.return_value = mock_generator

    # 模拟报告写入
    mock_writer = Mock()
    mock_writer.write.return_value = "/tmp/report.md"
    mock_writer_class.return_value = mock_writer

    # 导入并运行主函数
    import sys
    sys.argv = ["blog-research.py"]

    from blog_research import main
    main()

    # 验证调用
    mock_github.get_issues.assert_called_once()
    mock_evaluator.evaluate_batch.assert_called_once()
    mock_generator.generate.assert_called_once()
    mock_writer.write.assert_called_once()


def test_parse_args():
    """测试参数解析"""
    import sys
    sys.argv = ["blog-research.py", "--output", "/custom", "--threshold", "80"]

    from blog_research import parse_args
    args = parse_args()

    assert args.output == "/custom"
    assert args.threshold == 80
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/test_blog_research_cli.py -v`
Expected: FAIL with "Module not found"

- [ ] **Step 3: 创建 CLI 脚本**

Create: `blog-research.py`

```python
#!/usr/bin/env python3
"""博客标题优化与选题生成工具

基于 autoresearch 模式，批量评估博客标题质量并推荐新选题。

Usage:
    uv run blog-research.py
    uv run blog-research.py --output ./reports --threshold 80
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.escaping.config import ResearchConfig
from src.escaping.services.github_service import GitHubService
from src.escaping.research.title_evaluator import TitleEvaluator
from src.escaping.research.topic_generator import TopicGenerator
from src.escaping.research.report_writer import ReportWriter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="博客标题优化与选题生成工具"
    )
    parser.add_argument(
        "--output", "-o",
        default="./reports",
        help="报告输出目录 (默认: ./reports)"
    )
    parser.add_argument(
        "--threshold", "-t",
        type=int,
        default=75,
        help="优化建议阈值，低于此分数建议优化 (默认: 75)"
    )
    parser.add_argument(
        "--no-topics",
        action="store_true",
        help="不生成选题推荐"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细日志"
    )
    return parser.parse_args()


def progress_callback(current: int, total: int):
    """显示进度"""
    percent = current / total * 100
    print(f"\r评估进度: {current}/{total} ({percent:.1f}%)", end="", flush=True)
    if current == total:
        print()  # 换行


def main():
    """主入口"""
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # 1. 加载配置
        logger.info("加载配置...")
        config = ResearchConfig()
        config.output_dir = args.output

        # 2. 获取 GitHub Issues
        logger.info("获取博客文章...")
        github_token = os.getenv("G_T") or os.getenv("GITHUB_TOKEN")
        if not github_token:
            logger.error("错误: 需要设置 G_T 或 GITHUB_TOKEN 环境变量")
            sys.exit(1)

        # 从现有配置读取 repo
        from src.escaping.config import BlogConfig
        blog_config = BlogConfig()
        repo_name = blog_config.github.repo

        github_service = GitHubService(github_token)
        issues = github_service.get_issues(repo_name)

        if not issues:
            logger.warning("没有找到任何文章")
            sys.exit(0)

        logger.info(f"找到 {len(issues)} 篇文章")

        # 3. 评估标题
        logger.info("开始评估标题...")
        evaluator = TitleEvaluator(config)
        evaluations = evaluator.evaluate_batch(issues, progress_callback)

        # 4. 生成选题（如果不禁用）
        topics = []
        if not args.no_topics:
            logger.info("生成选题推荐...")
            generator = TopicGenerator(config)
            topics = generator.generate(issues)
            logger.info(f"生成 {len(topics)} 个选题建议")

        # 5. 分析标签分布
        tag_distribution = {}
        for issue in issues:
            for label in issue.get("labels", []):
                tag_distribution[label] = tag_distribution.get(label, 0) + 1

        # 6. 生成报告
        logger.info("生成报告...")
        writer = ReportWriter({"output_dir": args.output})
        report_path = writer.write(
            evaluations=evaluations,
            topics=topics,
            tag_distribution=tag_distribution,
            threshold=args.threshold
        )

        logger.info(f"报告已生成: {report_path}")

        # 7. 统计摘要
        need_improvement = sum(1 for e in evaluations if e.score < args.threshold)
        excellent = sum(1 for e in evaluations if e.score >= 90)
        avg_score = sum(e.score for e in evaluations) / len(evaluations) if evaluations else 0

        print("\n" + "=" * 50)
        print("评估摘要")
        print("=" * 50)
        print(f"总文章数: {len(evaluations)}")
        print(f"平均得分: {avg_score:.1f}")
        print(f"优秀标题: {excellent} 篇")
        print(f"建议优化: {need_improvement} 篇")
        print(f"新选题: {len(topics)} 个")
        print("=" * 50)
        print(f"\n详细报告: {report_path}")

        # 8. 自动打开（可选）
        if config.auto_open:
            import platform
            import subprocess

            system = platform.system()
            try:
                if system == "Darwin":  # macOS
                    subprocess.run(["open", report_path], check=False)
                elif system == "Linux":
                    subprocess.run(["xdg-open", report_path], check=False)
                elif system == "Windows":
                    subprocess.run(["start", report_path], shell=True, check=False)
            except Exception as e:
                logger.warning(f"自动打开报告失败: {e}")

    except ValueError as e:
        logger.error(f"配置错误: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception("运行失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 确保 research 模块 __init__.py 更新**

Verify `src/escaping/research/__init__.py`:

```python
"""博客研究工具模块"""

from src.escaping.research.title_evaluator import TitleEvaluator
from src.escaping.research.topic_generator import TopicGenerator
from src.escaping.research.report_writer import ReportWriter

__all__ = ["TitleEvaluator", "TopicGenerator", "ReportWriter"]
```

- [ ] **Step 5: 添加 reports 到 gitignore**

Edit `.gitignore`:

```
# Research reports
reports/
```

- [ ] **Step 6: 运行测试确认通过**

Run: `uv run pytest tests/test_blog_research_cli.py -v`
Expected: PASS (可能需要调整 mock)

- [ ] **Step 7: Commit**

```bash
git add blog-research.py tests/test_blog_research_cli.py .gitignore
git commit -m "feat: add blog-research CLI tool"
```

---

## Task 6: 集成测试与文档

**Files:**
- Create: `README_RESEARCH.md`

**目标:** 添加使用文档和最终验证

- [ ] **Step 1: 创建使用文档**

Create: `README_RESEARCH.md`

```markdown
# 博客标题优化工具

基于 Kimi API 的博客标题评估与选题推荐工具。

## 功能

- **批量评估**: 自动分析所有博客文章标题质量
- **优化建议**: 为低分标题生成 2-3 个优化候选
- **选题推荐**: 基于标签分布推荐新内容方向
- **Markdown 报告**: 输出详细的研究报告

## 安装

确保已安装依赖：

```bash
uv sync
```

## 配置

设置环境变量：

```bash
export MOONSHOT_API_KEY="your-api-key"
export G_T="your-github-token"  # 或 GITHUB_TOKEN
```

## 使用

### 基础运行

```bash
uv run blog-research.py
```

### 指定输出目录

```bash
uv run blog-research.py --output ./my-reports
```

### 调整评分阈值

```bash
uv run blog-research.py --threshold 80
```

### 只评估，不生成选题

```bash
uv run blog-research.py --no-topics
```

### 显示详细日志

```bash
uv run blog-research.py --verbose
```

## 评估维度

标题评分基于四个维度（各 25 分）：

1. **吸引力**: 是否激发点击欲望
2. **SEO友好度**: 关键词位置、搜索意图
3. **可读性**: 简洁明了、无歧义
4. **准确性**: 与内容匹配度

## 报告内容

生成的 Markdown 报告包含：

- 标题评分概览
- 需要优化的标题及建议
- 优秀标题参考
- 新选题推荐
- 标签分布分析
- 下一步行动建议

## 配置项

在 `config.yaml` 中添加：

```yaml
research:
  llm:
    provider: "moonshot"
    api_key_env: "MOONSHOT_API_KEY"
    base_url: "https://api.kimi.com/coding"
    temperature: 0.3
    max_tokens: 2000
  evaluation:
    min_score_threshold: 75
  output:
    dir: "./reports"
    auto_open: false
```
```

- [ ] **Step 2: 运行完整测试套件**

Run: `uv run pytest tests/ -v`
Expected: 所有测试通过

- [ ] **Step 3: 代码格式化检查**

Run: `uv run ruff check .`
Expected: 无错误

Run: `uv run ruff format .`
Expected: 格式化完成

- [ ] **Step 4: Commit**

```bash
git add README_RESEARCH.md
git commit -m "docs: add research tool usage documentation"
```

---

## 最终检查清单

- [ ] 所有单元测试通过
- [ ] 代码通过 ruff 检查
- [ ] 文档完整
- [ ] 可以成功运行 `uv run blog-research.py --help`

## 后续优化方向（可选）

1. **并发处理**: 使用 asyncio 并发调用 API
2. **缓存机制**: 缓存评估结果避免重复调用
3. **历史对比**: 对比多次评估结果的变化趋势
4. **交互式选择**: 提供交互式界面选择采纳哪些建议
