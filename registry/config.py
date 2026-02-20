"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Optional

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
    app_version: str = "0.1.0"
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


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
