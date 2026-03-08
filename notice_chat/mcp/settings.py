from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class SkuNoticeMCPSettings(BaseSettings):
    """Runtime settings for the SKU notice MCP server."""

    model_config = SettingsConfigDict(
        env_prefix="SKU_MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    server_name: str = "sku-notice-mcp"
    transport: Literal["stdio", "sse", "streamable-http"] = "stdio"
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


SKU_NOTICE_MCP_SETTINGS = SkuNoticeMCPSettings()
