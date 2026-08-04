from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """集中管理本地配置和项目路径。"""

    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[1])
    amap_web_key: str = ""
    amap_js_key: str = ""
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:0.5b"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def data_dir(self) -> Path:
        """返回项目的数据目录。"""
        return self.project_root / "data"
