import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class BlogConfig(BaseModel):
    """核心博客配置（必填）"""

    title: str
    description: str
    url: HttpUrl
    author: str


class GithubConfig(BaseModel):
    """GitHub 配置（必填）"""

    repo: str

    @property
    def name(self) -> str:
        """从 repo 解析用户名，如 'geoqiao/blog' -> 'geoqiao'"""
        return self.repo.split("/")[0] if "/" in self.repo else self.repo


class AboutLink(BaseModel):
    """关于页面链接"""

    name: str
    url: str


class AboutConfig(BaseModel):
    """关于页面配置（必填）"""

    avatar: str = ""  # 头像 URL，留空则不显示
    bio: str
    expertise: list[str] = Field(default_factory=list)
    links: list[AboutLink]


class ThemeConfig(BaseModel):
    """主题配置（可选，默认 BearMinimal）"""

    name: str = "BearMinimal"

    @property
    def path(self) -> Path:
        """主题路径，如 'BearMinimal' → templates/BearMinimal"""
        return Path("templates") / self.name

    @property
    def seo(self) -> Path:
        """SEO 模板路径"""
        return Path("templates/seo")

    @property
    def url_path(self) -> str:
        """URL 路径，如 /templates/BearMinimal"""
        return f"/templates/{self.name}"


class NavigationItem(BaseModel):
    """导航项"""

    name: str
    url: str


class NavigationConfig(BaseModel):
    """导航配置（可选）"""

    items: list[NavigationItem] = Field(default_factory=list)


class AdvancedConfig(BaseModel):
    """高级配置（可选，一般不需要修改）"""

    page_size: int = 10
    home_post_count: int = 10
    language: str = "en"


class GoogleSearchConsoleConfig(BaseModel):
    """Google Search Console 配置（可选）"""

    content: str = ""
    verify: bool = False


class Settings(BaseSettings):
    """应用配置"""

    # 核心配置（必填）
    blog: BlogConfig
    github: GithubConfig
    about: AboutConfig

    # 可选配置
    theme: ThemeConfig = Field(default_factory=ThemeConfig)
    navigation: NavigationConfig = Field(default_factory=NavigationConfig)
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)
    google_search_console: GoogleSearchConsoleConfig = Field(
        default_factory=GoogleSearchConsoleConfig,
        alias="GoogleSearchConsole",
    )

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_prefix="APP_",
        extra="ignore",
    )

    @classmethod
    def load_from_yaml(cls, yaml_path: Path) -> "Settings":
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)


# 全局配置实例
try:
    _settings = Settings.load_from_yaml(Path("config.yaml"))
except (FileNotFoundError, yaml.YAMLError) as e:
    # 允许测试或 CI 环境通过环境变量覆盖, 若 yaml 不存在则跳过
    logger.debug(f"Config load skipped: {e}")
    _settings = None


def get_settings() -> Settings:
    """获取应用配置。

    Raises:
        RuntimeError: 如果配置未加载成功。
    """
    if _settings is None:
        msg = "Settings not loaded. Ensure config.yaml exists or set environment variables."
        raise RuntimeError(msg)
    return _settings


# 向后兼容的导出
settings = _settings
