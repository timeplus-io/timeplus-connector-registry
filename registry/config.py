"""Application configuration using Pydantic Settings."""

import json
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Timeplus Connector Registry"
    app_version: str = "0.2.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database (embedded SQLite by default - no external dependencies required)
    database_url: str = "sqlite+aiosqlite:///./registry.db"

    # Security
    secret_key: str = "change-me-in-production-use-a-long-random-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # CORS
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:8000", "http://127.0.0.1:8000"]
    )
    cors_allow_credentials: bool = False

    # API
    api_v1_prefix: str = "/api/v1"

    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100

    # Storage
    storage_path: str = "./storage"

    # Rate limiting
    rate_limit_anonymous: int = 60  # per hour
    rate_limit_authenticated: int = 1000  # per hour
    rate_limit_window_seconds: int = 3600
    rate_limit_use_forwarded_for: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> Any:
        """Allow CORS origins to be provided as JSON or comma-separated env var."""
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                return json.loads(text)
            return [item.strip() for item in text.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        """Disallow obviously insecure production defaults."""
        if "*" in self.cors_origins and self.cors_allow_credentials:
            raise ValueError(
                "CORS misconfiguration: wildcard origins cannot be used with credentials enabled"
            )

        if self.rate_limit_anonymous <= 0:
            raise ValueError("RATE_LIMIT_ANONYMOUS must be > 0")

        if self.rate_limit_authenticated <= 0:
            raise ValueError("RATE_LIMIT_AUTHENTICATED must be > 0")

        if self.rate_limit_window_seconds <= 0:
            raise ValueError("RATE_LIMIT_WINDOW_SECONDS must be > 0")

        insecure_default = "change-me-in-production-use-a-long-random-string"
        if not self.debug and self.secret_key == insecure_default:
            raise ValueError(
                "SECRET_KEY must be explicitly configured when DEBUG is false"
            )

        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
