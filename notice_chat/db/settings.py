from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(env_prefix="DATABASE_")

    url: str = "sqlite+aiosqlite:///./local_database.db"


DATABASE_SETTINGS = DatabaseSettings()
