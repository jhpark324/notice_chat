from __future__ import annotations

from datetime import date

import pytest

from notice_chat.services import (
    NoticeSearchFilters,
    NoticeSearchResultItem,
    NoticeSearchService,
)

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _build_item(
    *,
    notice_id: int,
    source_notice_id: int,
    title: str,
    posted_date: date,
    keyword_score: float = 0.0,
    semantic_score: float = 0.0,
    reasons: list[str] | None = None,
) -> NoticeSearchResultItem:
    return NoticeSearchResultItem(
        id=notice_id,
        source_notice_id=source_notice_id,
        title=title,
        category="장학",
        author_org="학생처",
        posted_date=posted_date,
        status="진행중",
        detail_url=f"https://www.skuniv.ac.kr/notice/{source_notice_id}",
        summary_text="요약",
        keyword_score=keyword_score,
        semantic_score=semantic_score,
        match_reason=reasons or [],
    )


class _FakeTool:
    def __init__(self, results: list[NoticeSearchResultItem]) -> None:
        self._results = results

    async def search(self, *, query: str, filters: NoticeSearchFilters, top_k: int):  # noqa: ANN201
        _ = query, filters, top_k
        return self._results


class _RaisingTool:
    async def search(self, *, query: str, filters: NoticeSearchFilters, top_k: int):  # noqa: ANN201
        _ = query, filters, top_k
        raise RuntimeError("semantic backend unavailable")


async def test_search_notices_merges_hybrid_results() -> None:
    text_results = [
        _build_item(
            notice_id=1,
            source_notice_id=1001,
            title="장학금 신청 안내",
            posted_date=date(2026, 3, 8),
            keyword_score=3.0,
            reasons=["keyword:title"],
        ),
        _build_item(
            notice_id=2,
            source_notice_id=1002,
            title="수업 공지",
            posted_date=date(2026, 3, 7),
            keyword_score=1.0,
            reasons=["keyword:summary_text"],
        ),
    ]
    semantic_results = [
        _build_item(
            notice_id=1,
            source_notice_id=1001,
            title="장학금 신청 안내",
            posted_date=date(2026, 3, 8),
            semantic_score=0.9,
            reasons=["semantic:embedding"],
        ),
        _build_item(
            notice_id=3,
            source_notice_id=1003,
            title="기숙사 신청",
            posted_date=date(2026, 3, 6),
            semantic_score=0.8,
            reasons=["semantic:embedding"],
        ),
    ]

    service = NoticeSearchService(
        text_sql_tool=_FakeTool(text_results),
        semantic_tool=_FakeTool(semantic_results),
    )

    result = await service.search_notices(query="장학금", top_k=10)

    assert result["mode"] == "hybrid"
    assert result["total_returned"] == 3
    first = result["results"][0]
    assert first["source_notice_id"] == 1001
    assert "keyword:title" in first["match_reason"]
    assert "semantic:embedding" in first["match_reason"]


async def test_search_notices_keeps_sql_results_when_semantic_fails() -> None:
    text_results = [
        _build_item(
            notice_id=10,
            source_notice_id=2001,
            title="등록금 납부 안내",
            posted_date=date(2026, 3, 8),
            keyword_score=2.0,
            reasons=["keyword:title"],
        )
    ]
    service = NoticeSearchService(
        text_sql_tool=_FakeTool(text_results),
        semantic_tool=_RaisingTool(),
    )

    result = await service.search_notices(query="등록금", top_k=5)

    assert result["mode"] == "sql_only"
    assert result["total_returned"] == 1
    assert len(result["errors"]) == 1
    assert result["errors"][0].startswith("semantic:")


async def test_search_notices_can_hide_match_reason() -> None:
    text_results = [
        _build_item(
            notice_id=20,
            source_notice_id=3001,
            title="장학 안내",
            posted_date=date(2026, 3, 8),
            keyword_score=2.0,
            reasons=["keyword:title"],
        )
    ]
    service = NoticeSearchService(
        text_sql_tool=_FakeTool(text_results),
        semantic_tool=_FakeTool([]),
    )

    result = await service.search_notices(
        query="장학",
        top_k=5,
        include_reason=False,
    )

    assert result["mode"] == "sql_only"
    assert result["results"][0]["match_reason"] == []
