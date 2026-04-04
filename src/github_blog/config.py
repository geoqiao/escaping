import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class AuthorConfig(BaseModel):
    name: str
    email: str


class BlogConfig(BaseModel):
    title: str
    description: str
    url: HttpUrl
    content_dir: Path
    blog_dir: Path
    rss_atom_path: str
    author: AuthorConfig
    page_size: int


class GithubConfig(BaseModel):
    name: str
    repo: str


class GoogleSearchConsoleConfig(BaseModel):
    content: str
    verify: bool


class ThemeConfig(BaseModel):
    path: Path
    seo: Path = Path("templates/seo")

    @property
    def url_path(self) -> str:
        """将文件路径转换为 URL 路径（如 templates/PaperMint → /templates/PaperMint）。"""
        return "/" + str(self.path).strip("/")


class NavigationItem(BaseModel):
    name: str
    url: str


class NavigationConfig(BaseModel):
    items: list[NavigationItem] = Field(default_factory=list)


class HomeConfig(BaseModel):
    intro_line1: str = ""
    intro_line2: str = ""
    source_code_text: str = ""
    source_code_url: str = ""
    recent_posts_title: str = "Recent Posts"
    view_all_text: str = "View all posts →"
    post_count: int = 10


class AboutSection(BaseModel):
    title: str
    type: str  # paragraphs, list, contact
    content: list[str] = Field(default_factory=list)
    links: list[dict[str, str]] = Field(default_factory=list)


class AboutConfig(BaseModel):
    page_title: str = "About"
    sections: list[AboutSection] = Field(default_factory=list)


class PaginationConfig(BaseModel):
    prev_text: str = "← Prev"
    next_text: str = "Next →"


class TagsConfig(BaseModel):
    page_title: str = "Tags"


class Settings(BaseSettings):
    blog: BlogConfig
    github: GithubConfig
    google_search_console: GoogleSearchConsoleConfig = Field(
        alias="GoogleSearchConsole"
    )
    theme: ThemeConfig
    navigation: NavigationConfig = Field(default_factory=NavigationConfig)
    home: HomeConfig = Field(default_factory=HomeConfig)
    about: AboutConfig = Field(default_factory=AboutConfig)
    pagination: PaginationConfig = Field(default_factory=PaginationConfig)
    tags: TagsConfig = Field(default_factory=TagsConfig)

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
