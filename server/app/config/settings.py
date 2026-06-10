from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    port: int = Field(default=8000, ge=1, le=65535)
    app_name: str = "CVantage API"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    mongodb_uri: str = "mongodb://localhost:27017/cvantage"
    mongodb_db_name: str = "cvantage"
    ready_min_disk_free_mb: int = Field(default=128, ge=1)
    ready_min_memory_available_mb: int = Field(default=128, ge=1)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
