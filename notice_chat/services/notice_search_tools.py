from __future__ import annotations

import math
import re
from datetime import date
from typing import Protocol

from langsmith import traceable
from sqlalchemy.ext.asyncio import async_sessionmaker

from notice_chat.db import SessionLocal
from notice_chat.repositories import SkuNoticeRepository

from .notice_search_models import NoticeSearchFilters, NoticeSearchResultItem
from .sku_notice_embedding import (
    LangChainNoticeEmbeddingService,
    NoticeEmbeddingService,
)


class NoticeSearchTool(Protocol):
    async def search(
        self,
        *,
        query: str,
        filters: NoticeSearchFilters,
        top_k: int,
    ) -> list[NoticeSearchResultItem]:
        raise NotImplementedError


def _normalize_tokens(query: str) -> list[str]:
    return [token for token in re.split(r"\s+", query.lower().strip()) if token]


def _keyword_score(title: str, summary_text: str, query: str) -> float:
    tokens = _normalize_tokens(query)
    if not tokens:
        return 0.0

    title_lower = title.lower()
    summary_lower = summary_text.lower()
    score = 0.0
    for token in tokens:
        if token in title_lower:
            score += 2.0
        if token in summary_lower:
            score += 1.0
    return score


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


class TextSqlSearchTool:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker = SessionLocal,
    ) -> None:
        self.session_factory = session_factory

    @traceable(
        name="notice_search.text_sql_search",
        run_type="retriever",
        tags=["notice-search", "sql"],
    )
    async def search(
        self,
        *,
        query: str,
        filters: NoticeSearchFilters,
        top_k: int,
    ) -> list[NoticeSearchResultItem]:
        fetch_limit = max(top_k * 3, top_k)
        async with self.session_factory() as session:
            repository = SkuNoticeRepository(session)
            notices = await repository.search_text(
                query=query,
                limit=fetch_limit,
                category=filters.category,
                author_org=filters.author_org,
                posted_from=filters.posted_from,
                posted_to=filters.posted_to,
                status=filters.status,
            )

        results: list[NoticeSearchResultItem] = []
        for notice in notices:
            item = NoticeSearchResultItem.from_db(notice)
            item.keyword_score = _keyword_score(item.title, item.summary_text, query)

            if item.keyword_score > 0:
                if query.lower().strip() in item.title.lower():
                    item.match_reason.append("keyword:title")
                if query.lower().strip() in item.summary_text.lower():
                    item.match_reason.append("keyword:summary_text")
            results.append(item)

        results.sort(
            key=lambda item: (item.keyword_score, item.posted_date or date.min),
            reverse=True,
        )
        return results[:top_k]


class SemanticSearchTool:
    def __init__(
        self,
        *,
        embedding_service: NoticeEmbeddingService | None = None,
        session_factory: async_sessionmaker = SessionLocal,
        candidate_pool_size: int = 250,
    ) -> None:
        self.embedding_service = embedding_service or LangChainNoticeEmbeddingService()
        self.session_factory = session_factory
        self.candidate_pool_size = candidate_pool_size

    @traceable(
        name="notice_search.semantic_search",
        run_type="retriever",
        tags=["notice-search", "semantic"],
    )
    async def search(
        self,
        *,
        query: str,
        filters: NoticeSearchFilters,
        top_k: int,
    ) -> list[NoticeSearchResultItem]:
        query_vector = await self.embedding_service.embed_query(query)
        if query_vector is None:
            return []

        async with self.session_factory() as session:
            repository = SkuNoticeRepository(session)
            notices = await repository.list_semantic_candidates(
                limit=max(top_k * 4, self.candidate_pool_size),
                category=filters.category,
                author_org=filters.author_org,
                posted_from=filters.posted_from,
                posted_to=filters.posted_to,
                status=filters.status,
            )

        results: list[NoticeSearchResultItem] = []
        for notice in notices:
            if notice.embedding is None:
                continue
            semantic_score = _cosine_similarity(query_vector, notice.embedding)
            if semantic_score <= 0:
                continue
            item = NoticeSearchResultItem.from_db(notice)
            item.semantic_score = semantic_score
            item.match_reason.append("semantic:embedding")
            results.append(item)

        results.sort(
            key=lambda item: (item.semantic_score, item.posted_date or date.min),
            reverse=True,
        )
        return results[:top_k]
