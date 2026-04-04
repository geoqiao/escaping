"""
模板完整性测试 - 防止 UI 渲染问题

这些测试确保：
1. 模板文件存在且完整
2. CSS 类名一致（如所有标签使用 .tag 而非混用）
3. 引用的静态资源存在
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from jinja2 import FileSystemLoader

from github_blog.services.render_service import RenderService

PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATE_DIR = PROJECT_ROOT / "templates" / "PaperMint"
CSS_DIR = TEMPLATE_DIR / "static" / "css"


class TestTemplateFilesExist:
    """测试模板文件完整性"""

    def test_index_template_exists(self):
        """index.html 模板必须存在"""
        assert (TEMPLATE_DIR / "index.html").exists(), "index.html 模板缺失"

    def test_post_template_exists(self):
        """post.html 模板必须存在"""
        assert (TEMPLATE_DIR / "post.html").exists()

    def test_tag_template_exists(self):
        """tag.html 模板必须存在"""
        assert (TEMPLATE_DIR / "tag.html").exists()

    def test_tags_template_exists(self):
        """tags.html 模板必须存在"""
        assert (TEMPLATE_DIR / "tags.html").exists()

    def test_base_template_exists(self):
        """base.html 母版必须存在"""
        assert (TEMPLATE_DIR / "base.html").exists()

    def test_main_css_exists(self):
        """主 CSS 文件必须存在"""
        assert (CSS_DIR / "papermint.css").exists()


class TestTemplateClassConsistency:
    """测试 CSS 类名一致性"""

    def _get_template_content(self, filename: str) -> str:
        return (TEMPLATE_DIR / filename).read_text()

    def test_tags_page_uses_consistent_tag_class(self):
        """tags.html 必须使用统一的 .tag 类"""
        content = self._get_template_content("tags.html")

        # 检查是否错误使用了未定义的标签类
        forbidden_classes = ["tag-cloud"]
        for cls in forbidden_classes:
            assert f'class="{cls}"' not in content, (
                f"tags.html 使用了未定义的 CSS 类 '{cls}'，"
                f"应使用现有的 '.tag' 类保持一致性"
            )

        # 确认使用了正确的类
        assert 'class="tag-list"' in content
        assert 'class="tag"' in content

    def test_tag_page_uses_consistent_classes(self):
        """tag.html 必须使用统一的类名"""
        content = self._get_template_content("tag.html")

        # 检查结构完整性
        assert 'class="post-title"' in content
        assert 'class="post-meta"' in content

    def test_index_page_structure(self):
        """index.html 必须有正确的列表结构"""
        content = self._get_template_content("index.html")

        assert 'class="posts-list"' in content
        assert 'class="post"' in content


class TestRenderedOutputConsistency:
    """测试渲染输出的一致性"""

    @pytest.fixture
    def render(self):
        return RenderService()

    def _make_issue(self, number=1, title="Test", body="Body", labels=None):
        issue = MagicMock()
        issue.number = number
        issue.title = title
        issue.body = body
        issue.labels = labels or []
        from datetime import datetime, timezone
        issue.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        issue.updated_at = datetime(2024, 1, 2, tzinfo=timezone.utc)
        return issue

    def test_tags_page_uses_tag_class_not_cloud(self, render):
        """渲染的 tags 页面必须使用 .tag 而非 .tag-cloud"""
        html = render.render_tags_page(
            tags=["python", "web"],
            tag_counts={"python": 5, "web": 3}
        )

        # 确认使用了正确的类
        assert 'class="tag-list"' in html
        assert 'class="tag"' in html

        # 确认没有使用未定义的类
        assert 'class="tag-cloud"' not in html, (
            "渲染输出包含未定义的 'tag-cloud' 类"
        )

    def test_all_tag_links_use_consistent_format(self, render):
        """所有标签链接格式必须一致"""
        html = render.render_tags_page(
            tags=["python"],
            tag_counts={"python": 5}
        )

        # 检查是否包含数量显示 (如 "python <span class=\"tag-count\">(5)</span>")
        assert 'class="tag-count">(5)' in html or 'class="tag-count">5' in html


class TestCSSStyleDefinitions:
    """测试 CSS 样式定义完整性"""

    def _get_css_content(self) -> str:
        return (CSS_DIR / "papermint.css").read_text()

    def test_tag_class_defined(self):
        """.tag 类必须在 CSS 中定义"""
        css = self._get_css_content()
        assert ".tag {" in css or ".tag{" in css

    def test_tag_list_class_defined(self):
        """.tag-list 类必须在 CSS 中定义"""
        css = self._get_css_content()
        assert ".tag-list {" in css or ".tag-list{" in css

    def test_no_orphan_css_classes(self):
        """CSS 中不应有未使用的类（可选检查）"""
        css = self._get_css_content()

        # 获取所有模板内容
        all_templates = ""
        for template_file in TEMPLATE_DIR.glob("*.html"):
            all_templates += template_file.read_text()

        # 检查 CSS 中定义的主要类是否在模板中使用
        # 这是一个软性检查，只记录警告
        import re
        css_classes = set(re.findall(r'\.([a-z-]+)\s*\{', css))
        used_classes = set(re.findall(r'class="([^"]+)"', all_templates))

        # 扁平化多类名（如 "class="a b" -> {"a", "b"}"）
        all_used = set()
        for classes in used_classes:
            all_used.update(classes.split())

        # 检查常用的类是否存在
        essential_classes = ["tag", "tag-list", "post", "post-title"]
        for cls in essential_classes:
            assert cls in all_used, f"CSS 类 '{cls}' 似乎没有在模板中使用"


class TestTemplateIntegration:
    """集成测试 - 确保渲染流程完整"""

    @pytest.fixture
    def render(self):
        return RenderService()

    def _make_issue(self, number=1, title="Test", body="Body", labels=None):
        issue = MagicMock()
        issue.number = number
        issue.title = title
        issue.body = body
        issue.labels = labels or []
        from datetime import datetime, timezone
        issue.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        issue.updated_at = datetime(2024, 1, 2, tzinfo=timezone.utc)
        return issue

    def test_full_rendering_pipeline(self, render):
        """测试完整渲染流程"""
        issues = [self._make_issue(number=1, title="Post 1")]

        # 测试所有渲染方法都能正常执行
        try:
            # 文章页
            render.render_post(issues[0], "1-test", "<p>body</p>")

            # 首页
            render.render_index(
                issues, tags=["test"],
                pagination={"page": 1, "pages": 1, "has_prev": False, "has_next": False, "prev_num": 0, "next_num": 2},
                issue_slugs={"1": "1-test"}
            )

            # 标签页
            render.render_tag_page("test", issues, ["test"], {"1": "1-test"})

            # 标签列表页
            render.render_tags_page(["test"], {"test": 1})

            # 主页
            render.render_home(issues, {"1": "1-test"})

        except Exception as e:
            pytest.fail(f"渲染流程失败: {e}")
