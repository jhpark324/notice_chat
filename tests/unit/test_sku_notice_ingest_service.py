from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from unittest.mock import AsyncMock

import pytest

import notice_chat.services.sku_notice_ingest_service as ingest_module
from notice_chat.services import CrawledNotice, ListNoticeItem, SkuNoticeIngestService

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


class _DummyClientContext:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None


class _FakeCrawler:
    def __init__(
        self,
        list_items: list[ListNoticeItem],
        details: list[CrawledNotice],
        crawl_failures: list["_FakeCrawlFailure"] | None = None,
    ) -> None:
        self._list_items = list_items
        self._details = details
        self._crawl_failures = crawl_failures or []
        self.list_calls: list[int] = []
        self.detail_calls: list[tuple[int, int]] = []

    def build_client(self) -> _DummyClientContext:
        return _DummyClientContext()

    async def crawl_notice_list(
        self,
        client: object,  # noqa: ARG002
        *,
        pages_to_scan: int,
    ) -> list[ListNoticeItem]:
        self.list_calls.append(pages_to_scan)
        return self._list_items

    async def crawl_notice_details(
        self,
        client: object,  # noqa: ARG002
        items: list[ListNoticeItem],
        *,
        concurrency: int,
    ) -> tuple[list[CrawledNotice], list["_FakeCrawlFailure"]]:
        self.detail_calls.append((len(items), concurrency))
        return self._details, self._crawl_failures


@dataclass(slots=True)
class _FakeCrawlFailure:
    source_notice_id: int
    detail_url: str
    error: str


class _FakeSummaryService:
    def __init__(self) -> None:
        self.calls: list[int] = []

    async def summarize(self, notice: CrawledNotice) -> str:
        self.calls.append(notice.source_notice_id)
        return f"summary:{notice.source_notice_id}"


class _FakeEmbeddingService:
    def __init__(self) -> None:
        self.calls: list[int] = []

    async def embed_notice(
        self,
        notice: CrawledNotice,
        *,
        summary_text: str,  # noqa: ARG002
    ) -> list[float]:
        self.calls.append(notice.source_notice_id)
        return [float(notice.source_notice_id), 0.5]


def _build_list_item(notice_id: int) -> ListNoticeItem:
    return ListNoticeItem(
        source_notice_id=notice_id,
        detail_url=f"https://www.skuniv.ac.kr/notice/{notice_id}",
        title=f"title-{notice_id}",
        category="장학",
        author_org="학생처",
        posted_date=date(2026, 3, 8),
        status="진행중",
        list_number=1,
    )


def _build_detail(notice_id: int) -> CrawledNotice:
    return CrawledNotice(
        source_notice_id=notice_id,
        detail_url=f"https://www.skuniv.ac.kr/notice/{notice_id}",
        title=f"title-{notice_id}",
        category="장학",
        author_org="학생처",
        posted_date=date(2026, 3, 8),
        status="진행중",
        list_number=1,
        period_start=date(2026, 3, 8),
        period_end=date(2026, 3, 20),
        raw_text="공지 본문",
        image_urls=[],
        attachments=[],
    )


async def test_select_candidates_uses_scanned_window_and_existing_ids() -> None:
    items = [_build_list_item(15), _build_list_item(14), _build_list_item(13)]

    candidates, threshold = SkuNoticeIngestService._select_candidates(  # noqa: SLF001
        items,
        existing_ids={14},
        lookback_notice_id=0,
        max_candidates=None,
    )

    assert threshold == 15
    assert [item.source_notice_id for item in candidates] == [15, 13]


async def test_select_candidates_includes_forced_refresh_window() -> None:
    items = [_build_list_item(15), _build_list_item(14), _build_list_item(13)]

    candidates, threshold = SkuNoticeIngestService._select_candidates(  # noqa: SLF001
        items,
        existing_ids={15, 14, 13},
        lookback_notice_id=1,
        max_candidates=None,
    )

    assert threshold == 14
    assert [item.source_notice_id for item in candidates] == [15, 14]


async def test_run_executes_graph_and_persists_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    list_items = [_build_list_item(12), _build_list_item(11), _build_list_item(9)]
    details = [_build_detail(12), _build_detail(9)]
    fake_crawler = _FakeCrawler(list_items=list_items, details=details)
    fake_summary = _FakeSummaryService()
    fake_embedding = _FakeEmbeddingService()

    saved_payloads = []

    class _FakeRepository:
        def __init__(self, session: object) -> None:  # noqa: ARG002
            pass

        async def upsert_by_source_notice_id(self, payload):  # type: ignore[no-untyped-def]
            saved_payloads.append(payload)
            return payload

    class _DummySessionContext:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
            return None

    monkeypatch.setattr(ingest_module, "SkuNoticeRepository", _FakeRepository)
    monkeypatch.setattr(ingest_module, "SessionLocal", lambda: _DummySessionContext())
    monkeypatch.setattr(ingest_module, "init_db", AsyncMock())

    service = SkuNoticeIngestService(
        crawler=fake_crawler,  # type: ignore[arg-type]
        summary_service=fake_summary,  # type: ignore[arg-type]
        embedding_service=fake_embedding,  # type: ignore[arg-type]
        default_detail_concurrency=7,
    )
    monkeypatch.setattr(service, "get_db_max_source_notice_id", AsyncMock(return_value=11))
    monkeypatch.setattr(
        service,
        "get_existing_source_notice_ids",
        AsyncMock(return_value={11}),
    )

    result = await service.run(
        pages_to_scan=4,
        lookback_notice_id=0,
        max_candidates=2,
        detail_concurrency=3,
    )

    assert result["db_max_source_notice_id"] == 11
    assert result["incremental_threshold"] == 12
    assert result["crawled_list_rows"] == 3
    assert result["candidate_count"] == 2
    assert result["saved_count"] == 2
    assert result["embedded_count"] == 2
    assert result["failed"] == []
    assert fake_crawler.list_calls == [4]
    assert fake_crawler.detail_calls == [(2, 3)]
    assert fake_summary.calls == [12, 9]
    assert fake_embedding.calls == [12, 9]
    assert [payload.source_notice_id for payload in saved_payloads] == [12, 9]
    assert all(payload.embedding is not None for payload in saved_payloads)
    assert all(payload.embedding_updated_at is not None for payload in saved_payloads)


async def test_run_records_failure_when_summary_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    list_items = [_build_list_item(20)]
    details = [_build_detail(20)]
    fake_crawler = _FakeCrawler(list_items=list_items, details=details)

    class _RaisingSummaryService:
        async def summarize(self, notice: CrawledNotice) -> str:  # noqa: ARG002
            raise RuntimeError("summary failed")

    class _FakeRepository:
        def __init__(self, session: object) -> None:  # noqa: ARG002
            pass

        async def upsert_by_source_notice_id(self, payload):  # type: ignore[no-untyped-def]
            return payload

    class _DummySessionContext:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
            return None

    monkeypatch.setattr(ingest_module, "SkuNoticeRepository", _FakeRepository)
    monkeypatch.setattr(ingest_module, "SessionLocal", lambda: _DummySessionContext())
    monkeypatch.setattr(ingest_module, "init_db", AsyncMock())

    service = SkuNoticeIngestService(
        crawler=fake_crawler,  # type: ignore[arg-type]
        summary_service=_RaisingSummaryService(),  # type: ignore[arg-type]
    )
    monkeypatch.setattr(service, "get_db_max_source_notice_id", AsyncMock(return_value=0))
    monkeypatch.setattr(
        service,
        "get_existing_source_notice_ids",
        AsyncMock(return_value=set()),
    )

    result = await service.run()

    assert result["saved_count"] == 0
    assert result["embedded_count"] == 0
    assert len(result["failed"]) == 2
    assert result["failed"][0]["stage"] == "summarize"
    assert result["failed"][1]["stage"] == "persist"


async def test_run_keeps_processing_when_some_detail_crawls_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    list_items = [_build_list_item(30), _build_list_item(29)]
    details = [_build_detail(30)]
    crawl_failures = [
        _FakeCrawlFailure(
            source_notice_id=29,
            detail_url="https://www.skuniv.ac.kr/notice/29",
            error="httpx.ConnectError('boom')",
        )
    ]
    fake_crawler = _FakeCrawler(
        list_items=list_items,
        details=details,
        crawl_failures=crawl_failures,
    )
    fake_summary = _FakeSummaryService()
    fake_embedding = _FakeEmbeddingService()
    saved_payloads: list[object] = []

    class _FakeRepository:
        def __init__(self, session: object) -> None:  # noqa: ARG002
            pass

        async def upsert_by_source_notice_id(self, payload):  # type: ignore[no-untyped-def]
            saved_payloads.append(payload)
            return payload

    class _DummySessionContext:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
            return None

    monkeypatch.setattr(ingest_module, "SkuNoticeRepository", _FakeRepository)
    monkeypatch.setattr(ingest_module, "SessionLocal", lambda: _DummySessionContext())
    monkeypatch.setattr(ingest_module, "init_db", AsyncMock())

    service = SkuNoticeIngestService(
        crawler=fake_crawler,  # type: ignore[arg-type]
        summary_service=fake_summary,  # type: ignore[arg-type]
        embedding_service=fake_embedding,  # type: ignore[arg-type]
    )
    monkeypatch.setattr(service, "get_db_max_source_notice_id", AsyncMock(return_value=0))
    monkeypatch.setattr(
        service,
        "get_existing_source_notice_ids",
        AsyncMock(return_value=set()),
    )

    result = await service.run(max_candidates=10)

    assert result["saved_count"] == 1
    assert result["embedded_count"] == 1
    assert len(saved_payloads) == 1
    assert len(result["failed"]) == 1
    assert result["failed"][0]["stage"] == "crawl"
    assert result["failed"][0]["source_notice_id"] == 29
