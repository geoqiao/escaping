from pathlib import Path

import yaml
from pydantic import BaseModel, Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


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


class Settings(BaseSettings):
    blog: BlogConfig
    github: GithubConfig
    google_search_console: GoogleSearchConsoleConfig = Field(
        alias="GoogleSearchConsole"
    )
    theme: ThemeConfig

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
    settings = Settings.load_from_yaml(Path("config.yaml"))
except Exception:
    # 允许测试或 CI 环境通过环境变量覆盖，若 yaml 不存在则跳过
    pass
