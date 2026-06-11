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
    auth_jwt_issuer: str = "cvantage-api"
    auth_jwt_audience: str = "cvantage-clients"
    auth_refresh_token_ttl_days: int = Field(default=30, ge=1)
    auth_refresh_cookie_name: str = "cv_refresh_token"
    auth_cookie_secure: bool = True
    oauth_callback_base_url: str = "http://localhost:8000/api/v1/auth/oauth"
    oauth_google_client_id: str | None = None
    oauth_google_client_secret: str | None = None
    oauth_linkedin_client_id: str | None = None
    oauth_linkedin_client_secret: str | None = None
    mail_driver: Literal["console", "smtp"] = "console"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "noreply@cvantage.local"
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
    auth_lockout_failure_threshold: int = Field(default=5, ge=2)
    auth_lockout_backoff_base_seconds: int = Field(default=30, ge=1)
    auth_lockout_backoff_max_seconds: int = Field(default=900, ge=1)
    master_encryption_key: str = Field(
        default="",
        description="32-byte base64-encoded key for AES-256-GCM encryption of provider API keys",
    )
    openai_api_key: str | None = Field(
        default=None, description="OpenAI API key (env fallback for AI models)"
    )
    # SPA serving (issue #92) — single-server production serves frontend/dist.
    serve_spa: bool | None = None
    spa_dist_dir: str = Field(default="../frontend/dist")

    storage_driver: str = Field(default="local", pattern=r"^(local|s3)$")
    storage_local_dir: str = Field(default="./data/uploads")
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None

    # LLM tuning + cost guards (issue #54)
    llm_timeout_seconds: int = Field(default=60, ge=1, le=600)
    llm_max_output_tokens: int = Field(default=2048, ge=64, le=32_000)
    analysis_max_jd_chars: int = Field(default=50_000, ge=100)
    analysis_max_resume_chars: int = Field(default=200_000, ge=100)
    max_concurrent_analyses_per_user: int = Field(default=3, ge=1, le=50)

    # LLM observability (all optional / env-gated — zero overhead when unset)
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_project: str | None = None
    langsmith_endpoint: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None

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

    @property
    def is_spa_enabled(self) -> bool:
        if self.serve_spa is not None:
            return self.serve_spa
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
