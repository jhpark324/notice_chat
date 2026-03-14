from __future__ import annotations

import os

import pytest

from notice_chat.observability import LangSmithSettings, configure_langsmith

pytestmark = [pytest.mark.unit]


def test_configure_langsmith_sets_expected_env_vars(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_ENDPOINT", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    monkeypatch.delenv("LANGSMITH_WORKSPACE_ID", raising=False)

    settings = LangSmithSettings(
        tracing=True,
        api_key="test-api-key",
        endpoint="https://api.smith.langchain.com",
        project="notice-chat",
        workspace_id="workspace-123",
    )

    configure_langsmith(settings)

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_TRACING_V2"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "test-api-key"
    assert os.environ["LANGSMITH_ENDPOINT"] == "https://api.smith.langchain.com"
    assert os.environ["LANGSMITH_PROJECT"] == "notice-chat"
    assert os.environ["LANGSMITH_WORKSPACE_ID"] == "workspace-123"


def test_configure_langsmith_clears_optional_env_vars(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("LANGSMITH_API_KEY", "stale-key")
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://stale.example.com")
    monkeypatch.setenv("LANGSMITH_PROJECT", "stale-project")
    monkeypatch.setenv("LANGSMITH_WORKSPACE_ID", "stale-workspace")

    settings = LangSmithSettings(
        tracing=False,
        api_key=None,
        endpoint=None,
        project=None,
        workspace_id=None,
    )

    configure_langsmith(settings)

    assert os.environ["LANGSMITH_TRACING"] == "false"
    assert os.environ["LANGSMITH_TRACING_V2"] == "false"
    assert "LANGSMITH_API_KEY" not in os.environ
    assert "LANGSMITH_ENDPOINT" not in os.environ
    assert "LANGSMITH_PROJECT" not in os.environ
    assert "LANGSMITH_WORKSPACE_ID" not in os.environ
