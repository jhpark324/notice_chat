from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest

import notice_chat.mcp.server as server_module
from notice_chat.mcp.server import create_notice_mcp_server

pytestmark = [pytest.mark.unit]


class _FakeSearchService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def search_notices(self, **kwargs):  # noqa: ANN003, ANN201
        self.calls.append(kwargs)
        return {
            "query": kwargs["query"],
            "applied_filters": kwargs["filters"].to_dict(),
            "mode": "hybrid",
            "results": [
                {
                    "id": 1,
                    "source_notice_id": 101,
                    "title": "장학금 신청 안내",
                    "category": "학생",
                    "author_org": "학생처",
                    "posted_date": date(2026, 3, 9),
                    "status": "진행중",
                    "detail_url": "https://www.skuniv.ac.kr/notice/101",
                    "summary_text": "요약",
                    "score": 1.0,
                    "keyword_score": 1.0,
                    "semantic_score": 0.8,
                    "recency_score": 0.9,
                    "match_reason": ["keyword:title"],
                }
            ],
            "total_returned": 1,
            "errors": [],
        }


class _FakeSessionContext:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001, ANN201
        _ = exc_type, exc, tb


def _fake_session_factory() -> _FakeSessionContext:
    return _FakeSessionContext()


class _FakeRepository:
    list_calls: list[dict[str, object]] = []
    detail_calls: list[int] = []

    def __init__(self, session: object) -> None:
        self._session = session

    async def get_by_source_notice_id(self, source_notice_id: int):  # noqa: ANN201
        _ = self._session
        self.__class__.detail_calls.append(source_notice_id)
        if source_notice_id != 101:
            return None
        return SimpleNamespace(
            id=1,
            source_notice_id=101,
            detail_url="https://www.skuniv.ac.kr/notice/101",
            title="장학금 신청 안내",
            category="학생",
            author_org="학생처",
            posted_date=date(2026, 3, 9),
            status="진행중",
            list_number=10,
            period_start=date(2026, 3, 10),
            period_end=date(2026, 3, 20),
            summary_text="요약",
            attachments=[{"file_name": "안내문.pdf"}],
            embedding=[0.1, 0.2],
            embedding_updated_at=datetime(2026, 3, 9, 9, 0, 0),
            created_at=datetime(2026, 3, 9, 8, 0, 0),
            updated_at=datetime(2026, 3, 9, 8, 30, 0),
        )

    async def list(
        self,
        *,
        limit: int,
        offset: int,
        category: str | None,
        status: str | None,
    ):  # noqa: ANN201
        _ = self._session
        self.__class__.list_calls.append(
            {
                "limit": limit,
                "offset": offset,
                "category": category,
                "status": status,
            }
        )
        return [
            SimpleNamespace(
                id=1,
                source_notice_id=101,
                detail_url="https://www.skuniv.ac.kr/notice/101",
                title="장학금 신청 안내",
                category="학생",
                author_org="학생처",
                posted_date=date(2026, 3, 9),
                status="진행중",
                list_number=10,
                period_start=None,
                period_end=None,
                summary_text="요약",
                attachments=None,
                embedding=None,
                embedding_updated_at=None,
                created_at=datetime(2026, 3, 9, 8, 0, 0),
                updated_at=datetime(2026, 3, 9, 8, 30, 0),
            )
        ]


async def _call_structured(
    server, name: str, arguments: dict[str, object]
) -> dict[str, Any]:
    result = await server.call_tool(name, arguments)
    assert isinstance(result, tuple)
    return cast(dict[str, Any], result[1])


@pytest.mark.asyncio
async def test_search_notices_tool_uses_filters_and_serializes_dates() -> None:
    search_service = _FakeSearchService()
    server = create_notice_mcp_server(
        search_service=search_service,
        session_factory=_fake_session_factory,
        repository_factory=_FakeRepository,
        enable_lifespan=False,
    )

    output = await _call_structured(
        server,
        "search_notices",
        {
            "query": "장학금",
            "top_k": 5,
            "category": "학생",
            "posted_from": "2026-03-01",
            "posted_to": "2026-03-31",
            "include_reason": True,
        },
    )

    assert output["total_returned"] == 1
    result_item = output["results"][0]
    assert result_item["posted_date"] == "2026-03-09"
    assert search_service.calls[0]["top_k"] == 5
    filters = search_service.calls[0]["filters"]
    assert filters.posted_from == date(2026, 3, 1)
    assert filters.posted_to == date(2026, 3, 31)


@pytest.mark.asyncio
async def test_list_and_detail_tools_return_structured_payloads() -> None:
    _FakeRepository.list_calls.clear()
    _FakeRepository.detail_calls.clear()
    server = create_notice_mcp_server(
        search_service=_FakeSearchService(),
        session_factory=_fake_session_factory,
        repository_factory=_FakeRepository,
        enable_lifespan=False,
    )

    listing = await _call_structured(
        server,
        "list_recent_notices",
        {"limit": 20, "offset": 0, "category": "학생", "status": "진행중"},
    )
    detail = await _call_structured(server, "get_notice_detail", {"source_notice_id": 101})

    assert listing["count"] == 1
    assert listing["items"][0]["posted_date"] == "2026-03-09"
    assert _FakeRepository.list_calls[0]["category"] == "학생"
    assert detail["found"] is True
    assert detail["notice"]["has_embedding"] is True
    assert _FakeRepository.detail_calls == [101]


def test_configure_windows_event_loop_policy_sets_selector(monkeypatch) -> None:  # noqa: ANN001
    applied: list[object] = []

    class _FakePolicy:
        pass

    monkeypatch.setattr(server_module.os, "name", "nt", raising=False)
    monkeypatch.setattr(
        server_module.asyncio,
        "WindowsSelectorEventLoopPolicy",
        _FakePolicy,
        raising=False,
    )
    monkeypatch.setattr(
        server_module.asyncio,
        "set_event_loop_policy",
        lambda policy: applied.append(policy),
    )

    server_module._configure_windows_event_loop_policy()

    assert len(applied) == 1
    assert isinstance(applied[0], _FakePolicy)
