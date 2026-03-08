from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="DATABASE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # SQLAlchemy async URL (example: postgresql+psycopg://user:pass@localhost:5432/db)
    url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/notice_chat"


DATABASE_SETTINGS = DatabaseSettings()
