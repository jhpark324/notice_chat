from __future__ import annotations

import os

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LangSmithSettings(BaseSettings):
    """Runtime settings for LangSmith tracing."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    tracing: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "LANGSMITH_TRACING",
            "LANGSMITH_TRACING_V2",
        ),
    )
    api_key: str | None = Field(default=None, validation_alias="LANGSMITH_API_KEY")
    endpoint: str | None = Field(default=None, validation_alias="LANGSMITH_ENDPOINT")
    project: str | None = Field(default=None, validation_alias="LANGSMITH_PROJECT")
    workspace_id: str | None = Field(
        default=None,
        validation_alias="LANGSMITH_WORKSPACE_ID",
    )


LANGSMITH_SETTINGS = LangSmithSettings()


def _set_optional_env(name: str, value: str | None) -> None:
    if value:
        os.environ[name] = value
        return
    os.environ.pop(name, None)


def configure_langsmith(
    settings: LangSmithSettings | None = None,
) -> LangSmithSettings:
    """Normalize LangSmith settings into process env vars for LangChain integrations."""

    resolved_settings = settings or LANGSMITH_SETTINGS

    tracing_value = "true" if resolved_settings.tracing else "false"
    os.environ["LANGSMITH_TRACING"] = tracing_value
    os.environ["LANGSMITH_TRACING_V2"] = tracing_value
    _set_optional_env("LANGSMITH_API_KEY", resolved_settings.api_key)
    _set_optional_env("LANGSMITH_ENDPOINT", resolved_settings.endpoint)
    _set_optional_env("LANGSMITH_PROJECT", resolved_settings.project)
    _set_optional_env("LANGSMITH_WORKSPACE_ID", resolved_settings.workspace_id)

    return resolved_settings
