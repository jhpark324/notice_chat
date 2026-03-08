from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class SkuNoticeSummarySettings(BaseSettings):
    """Runtime settings for notice summary generation."""

    model_config = SettingsConfigDict(
        env_prefix="SKU_SUMMARY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    model: str = "gpt-5-nano"
    temperature: float = 0.0
    max_input_chars: int = 12000
    fallback_chars: int = 2500


SKU_NOTICE_SUMMARY_SETTINGS = SkuNoticeSummarySettings()
