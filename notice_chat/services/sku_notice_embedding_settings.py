from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class SkuNoticeEmbeddingSettings(BaseSettings):
    """Runtime settings for notice embedding generation."""

    model_config = SettingsConfigDict(
        env_prefix="SKU_EMBEDDING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model: str = "text-embedding-3-large"
    dimensions: int = 1536
    max_input_chars: int = 12000


SKU_NOTICE_EMBEDDING_SETTINGS = SkuNoticeEmbeddingSettings()
