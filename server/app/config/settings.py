from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
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
    swagger_enabled: bool | None = None
    admin_email: str | None = None
    admin_password: str | None = None
    auth_access_token_secret: str = "dev-auth-secret-change-me"
    auth_access_token_ttl_seconds: int = Field(default=900, ge=60)
    mongodb_uri: str = "mongodb://localhost:27017/cvantage"
    mongodb_db_name: str = "cvantage"
    ready_min_disk_free_mb: int = Field(default=128, ge=1)
    ready_min_memory_available_mb: int = Field(default=128, ge=1)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    max_request_body_bytes: int = Field(default=2_000_000, ge=1_024)
    rate_limit_global: str = "200/minute"
    rate_limit_auth: str = "60/minute"
    rate_limit_upload: str = "20/minute"
    rate_limit_analysis: str = "10/minute"
    shutdown_timeout_ms: int = Field(default=10_000, ge=100)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_swagger_enabled(self) -> bool:
        if self.swagger_enabled is not None:
            return self.swagger_enabled
        return self.environment != "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
