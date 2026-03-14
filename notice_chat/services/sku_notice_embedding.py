from __future__ import annotations

import logging
import os
from typing import Any, Protocol

from langsmith import traceable
from langchain_openai import OpenAIEmbeddings

from .sku_notice_crawler import CrawledNotice
from .sku_notice_embedding_settings import (
    SKU_NOTICE_EMBEDDING_SETTINGS,
    SkuNoticeEmbeddingSettings,
)

logger = logging.getLogger(__name__)


def truncate_text(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + "..."


class NoticeEmbeddingService(Protocol):
    async def embed_query(self, query: str) -> list[float] | None:
        raise NotImplementedError

    @traceable(
        name="notice_embedding.embed_notice",
        run_type="embedding",
        tags=["embedding", "notice"],
    )
    async def embed_notice(
        self,
        notice: CrawledNotice,
        *,
        summary_text: str,
    ) -> list[float] | None:
        raise NotImplementedError


class LangChainNoticeEmbeddingService:
    def __init__(
        self,
        *,
        model: str | None = None,
        dimensions: int | None = None,
        max_input_chars: int | None = None,
        settings: SkuNoticeEmbeddingSettings | None = None,
        embedding_client: Any | None = None,
    ) -> None:
        resolved_settings = settings or SKU_NOTICE_EMBEDDING_SETTINGS
        self.model = model if model is not None else resolved_settings.model
        self.dimensions = (
            dimensions if dimensions is not None else resolved_settings.dimensions
        )
        self.max_input_chars = (
            max_input_chars
            if max_input_chars is not None
            else resolved_settings.max_input_chars
        )

        if embedding_client is not None:
            self._embeddings = embedding_client
        elif os.getenv("OPENAI_API_KEY"):
            self._embeddings = OpenAIEmbeddings(
                model=self.model,
                dimensions=self.dimensions,
            )
        else:
            self._embeddings = None

    @staticmethod
    def _format_attachments(notice: CrawledNotice) -> str:
        if not notice.attachments:
            return "- none"
        return "\n".join(
            f"- {attachment.get('file_name', '(unknown)')} ({attachment.get('file_url', '')})"
            for attachment in notice.attachments
        )

    def _build_embedding_text(self, notice: CrawledNotice, *, summary_text: str) -> str:
        return truncate_text(
            (
                f"[제목] {notice.title}\n"
                f"[분류] {notice.category}\n"
                f"[작성부서] {notice.author_org}\n"
                f"[게시일] {notice.posted_date}\n"
                f"[상태] {notice.status}\n"
                f"[기간] {notice.period_start} ~ {notice.period_end}\n"
                f"[요약]\n{summary_text}\n"
                f"[첨부파일]\n{self._format_attachments(notice)}\n"
                f"[본문]\n{notice.raw_text}"
            ),
            self.max_input_chars,
        )

    async def embed_notice(
        self,
        notice: CrawledNotice,
        *,
        summary_text: str,
    ) -> list[float] | None:
        if self._embeddings is None:
            return None

        text = self._build_embedding_text(notice, summary_text=summary_text)
        try:
            vector = await self._embeddings.aembed_query(text)
            return [float(value) for value in vector]
        except Exception:
            logger.exception(
                "Embedding generation failed for source_notice_id=%s",
                notice.source_notice_id,
            )
            return None

    @traceable(
        name="notice_embedding.embed_query",
        run_type="embedding",
        tags=["embedding", "query"],
    )
    async def embed_query(self, query: str) -> list[float] | None:
        if self._embeddings is None:
            return None

        normalized_query = query.strip()
        if not normalized_query:
            return None

        try:
            vector = await self._embeddings.aembed_query(
                truncate_text(normalized_query, self.max_input_chars)
            )
            return [float(value) for value in vector]
        except Exception:
            logger.exception("Query embedding generation failed")
            return None
