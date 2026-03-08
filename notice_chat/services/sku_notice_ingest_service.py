from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import func, select

from notice_chat.db import SessionLocal, init_db
from notice_chat.models import DBSkuNotice
from notice_chat.repositories import SkuNoticeRepository
from notice_chat.schemas import SkuNoticeCreate

from .sku_notice_crawler import CrawledNotice, ListNoticeItem, SkuNoticeCrawler
from .sku_notice_embedding import (
    LangChainNoticeEmbeddingService,
    NoticeEmbeddingService,
)
from .sku_notice_summary import LangChainNoticeSummaryService, NoticeSummaryService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SkuNoticeIngestResult:
    db_max_source_notice_id: int
    incremental_threshold: int
    crawled_list_rows: int
    candidate_count: int
    saved_count: int
    embedded_count: int
    failed: list[dict[str, Any]]


class SkuNoticeIngestState(TypedDict, total=False):
    pages_to_scan: int
    lookback_notice_id: int
    max_candidates: int | None
    detail_concurrency: int
    db_max_source_notice_id: int
    incremental_threshold: int
    list_items: list[ListNoticeItem]
    candidates: list[ListNoticeItem]
    details: list[CrawledNotice]
    summaries: dict[int, str]
    crawled_list_rows: int
    candidate_count: int
    saved_count: int
    embedded_count: int
    failed: list[dict[str, Any]]


class SkuNoticeIngestService:
    def __init__(
        self,
        *,
        crawler: SkuNoticeCrawler | None = None,
        summary_service: NoticeSummaryService | None = None,
        embedding_service: NoticeEmbeddingService | None = None,
        default_detail_concurrency: int = 5,
    ) -> None:
        self.crawler = crawler or SkuNoticeCrawler()
        self.summary_service = summary_service or LangChainNoticeSummaryService()
        self.embedding_service = embedding_service or LangChainNoticeEmbeddingService()
        self.default_detail_concurrency = default_detail_concurrency
        self._graph = self._build_graph()

    async def get_db_max_source_notice_id(self) -> int:
        async with SessionLocal() as session:
            value = await session.scalar(select(func.max(DBSkuNotice.source_notice_id)))
            return int(value) if value is not None else 0

    @staticmethod
    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _to_payload(
        detail: CrawledNotice,
        summary_text: str,
        embedding: list[float] | None,
    ) -> SkuNoticeCreate:
        return SkuNoticeCreate(
            source_notice_id=detail.source_notice_id,
            detail_url=detail.detail_url,
            title=detail.title,
            category=detail.category,
            author_org=detail.author_org,
            posted_date=detail.posted_date,
            status=detail.status,
            list_number=detail.list_number,
            period_start=detail.period_start,
            period_end=detail.period_end,
            summary_text=summary_text,
            attachments=detail.attachments or None,
            embedding=embedding,
            embedding_updated_at=(
                SkuNoticeIngestService._utcnow() if embedding is not None else None
            ),
        )

    @staticmethod
    def _select_candidates(
        items: list[ListNoticeItem],
        *,
        threshold: int,
        max_candidates: int | None,
    ) -> list[ListNoticeItem]:
        candidates = [item for item in items if item.source_notice_id >= threshold]
        candidates = sorted(candidates, key=lambda item: item.source_notice_id, reverse=True)
        if max_candidates is not None:
            candidates = candidates[:max_candidates]
        return candidates

    def _build_graph(self):
        workflow = StateGraph(SkuNoticeIngestState)
        workflow.add_node("crawl", self._crawl_node)
        workflow.add_node("summarize", self._summarize_node)
        workflow.add_node("persist", self._persist_node)
        workflow.add_edge(START, "crawl")
        workflow.add_edge("crawl", "summarize")
        workflow.add_edge("summarize", "persist")
        workflow.add_edge("persist", END)
        return workflow.compile()

    async def _crawl_node(
        self, state: SkuNoticeIngestState
    ) -> SkuNoticeIngestState:
        pages_to_scan = state.get("pages_to_scan", 3)
        lookback_notice_id = state.get("lookback_notice_id", 0)
        max_candidates = state.get("max_candidates", 20)
        detail_concurrency = state.get(
            "detail_concurrency", self.default_detail_concurrency
        )

        db_max_id = await self.get_db_max_source_notice_id()
        threshold = max(0, db_max_id - lookback_notice_id)

        logger.info(
            "Crawl node start: db_max_source_notice_id=%s threshold=%s",
            db_max_id,
            threshold,
        )

        async with self.crawler.build_client() as client:
            list_items = await self.crawler.crawl_notice_list(
                client,
                pages_to_scan=pages_to_scan,
            )
            candidates = self._select_candidates(
                list_items,
                threshold=threshold,
                max_candidates=max_candidates,
            )
            details = (
                await self.crawler.crawl_notice_details(
                    client,
                    candidates,
                    concurrency=detail_concurrency,
                )
                if candidates
                else []
            )

        return {
            "db_max_source_notice_id": db_max_id,
            "incremental_threshold": threshold,
            "list_items": list_items,
            "candidates": candidates,
            "details": details,
            "crawled_list_rows": len(list_items),
            "candidate_count": len(candidates),
            "failed": [],
            "saved_count": 0,
            "embedded_count": 0,
        }

    async def _summarize_node(
        self, state: SkuNoticeIngestState
    ) -> SkuNoticeIngestState:
        details = state.get("details", [])
        failed = list(state.get("failed", []))
        summaries: dict[int, str] = {}

        for detail in details:
            try:
                summaries[detail.source_notice_id] = await self.summary_service.summarize(
                    detail
                )
            except Exception as exc:
                failed.append(
                    {
                        "stage": "summarize",
                        "source_notice_id": detail.source_notice_id,
                        "detail_url": detail.detail_url,
                        "error": repr(exc),
                    }
                )
                logger.exception(
                    "Summarize node failed for source_notice_id=%s",
                    detail.source_notice_id,
                )

        return {
            "summaries": summaries,
            "failed": failed,
        }

    async def _persist_node(
        self, state: SkuNoticeIngestState
    ) -> SkuNoticeIngestState:
        details = state.get("details", [])
        summaries = state.get("summaries", {})
        failed = list(state.get("failed", []))
        saved_count = 0
        embedded_count = 0

        if not details:
            return {
                "saved_count": 0,
                "embedded_count": 0,
                "failed": failed,
            }

        async with SessionLocal() as session:
            repository = SkuNoticeRepository(session)
            for detail in details:
                summary_text = summaries.get(detail.source_notice_id)
                if summary_text is None:
                    failed.append(
                        {
                            "stage": "persist",
                            "source_notice_id": detail.source_notice_id,
                            "detail_url": detail.detail_url,
                            "error": "missing summary",
                        }
                    )
                    continue

                try:
                    embedding = await self.embedding_service.embed_notice(
                        detail,
                        summary_text=summary_text,
                    )
                    if embedding is not None:
                        embedded_count += 1
                    payload = self._to_payload(detail, summary_text, embedding)
                    await repository.upsert_by_source_notice_id(payload)
                    saved_count += 1
                except Exception as exc:
                    failed.append(
                        {
                            "stage": "persist",
                            "source_notice_id": detail.source_notice_id,
                            "detail_url": detail.detail_url,
                            "error": repr(exc),
                        }
                    )
                    logger.exception(
                        "Persist node failed for source_notice_id=%s",
                        detail.source_notice_id,
                    )

        return {
            "saved_count": saved_count,
            "embedded_count": embedded_count,
            "failed": failed,
        }

    async def run(
        self,
        *,
        pages_to_scan: int = 3,
        lookback_notice_id: int = 0,
        max_candidates: int | None = 20,
        detail_concurrency: int | None = None,
    ) -> dict[str, Any]:
        await init_db()

        logger.info("Ingest workflow start")
        final_state = await self._graph.ainvoke(
            {
                "pages_to_scan": pages_to_scan,
                "lookback_notice_id": lookback_notice_id,
                "max_candidates": max_candidates,
                "detail_concurrency": detail_concurrency
                or self.default_detail_concurrency,
            }
        )

        result = SkuNoticeIngestResult(
            db_max_source_notice_id=final_state.get("db_max_source_notice_id", 0),
            incremental_threshold=final_state.get("incremental_threshold", 0),
            crawled_list_rows=final_state.get("crawled_list_rows", 0),
            candidate_count=final_state.get("candidate_count", 0),
            saved_count=final_state.get("saved_count", 0),
            embedded_count=final_state.get("embedded_count", 0),
            failed=final_state.get("failed", []),
        )
        logger.info(
            "Ingest complete: crawled=%s candidates=%s saved=%s embedded=%s failed=%s",
            result.crawled_list_rows,
            result.candidate_count,
            result.saved_count,
            result.embedded_count,
            len(result.failed),
        )
        return asdict(result)
