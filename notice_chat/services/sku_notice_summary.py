from __future__ import annotations

import logging
import os
from typing import Any, Protocol

from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from .sku_notice_crawler import CrawledNotice
from .sku_notice_summary_prompt import SKU_NOTICE_SUMMARY_PROMPT
from .sku_notice_summary_settings import (
    SKU_NOTICE_SUMMARY_SETTINGS,
    SkuNoticeSummarySettings,
)

logger = logging.getLogger(__name__)


def truncate_text(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + "..."


class NoticeSummaryService(Protocol):
    async def summarize(self, notice: CrawledNotice) -> str:
        raise NotImplementedError


class LangChainNoticeSummaryService:
    def __init__(
        self,
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_input_chars: int | None = None,
        fallback_chars: int | None = None,
        settings: SkuNoticeSummarySettings | None = None,
    ) -> None:
        resolved_settings = settings or SKU_NOTICE_SUMMARY_SETTINGS
        self._chain: Any | None = None
        self.max_input_chars = (
            max_input_chars
            if max_input_chars is not None
            else resolved_settings.max_input_chars
        )
        self.fallback_chars = (
            fallback_chars if fallback_chars is not None else resolved_settings.fallback_chars
        )
        self.model = model if model is not None else resolved_settings.model
        resolved_temperature = (
            temperature if temperature is not None else resolved_settings.temperature
        )

        if os.getenv("OPENAI_API_KEY"):
            llm = ChatOpenAI(model=self.model, temperature=resolved_temperature)
            self._chain = SKU_NOTICE_SUMMARY_PROMPT | llm | StrOutputParser()

    @staticmethod
    def _format_attachments(notice: CrawledNotice) -> str:
        if not notice.attachments:
            return "- none"
        return "\n".join(
            f"- {attachment.get('file_name', '(unknown)')} ({attachment.get('file_url', '')})"
            for attachment in notice.attachments
        )

    def _fallback_summary(self, notice: CrawledNotice) -> str:
        source = notice.raw_text or notice.title
        return truncate_text(source, self.fallback_chars)

    async def summarize(self, notice: CrawledNotice) -> str:
        if self._chain is None:
            return self._fallback_summary(notice)

        try:
            summary = await self._chain.ainvoke(
                {
                    "title": notice.title,
                    "detail_url": notice.detail_url,
                    "category": notice.category,
                    "author_org": notice.author_org,
                    "posted_date": notice.posted_date,
                    "status": notice.status,
                    "period_start": notice.period_start,
                    "period_end": notice.period_end,
                    "attachments": self._format_attachments(notice),
                    "raw_text": truncate_text(notice.raw_text, self.max_input_chars),
                }
            )
            cleaned = summary.strip()
            return cleaned if cleaned else self._fallback_summary(notice)
        except Exception:
            logger.exception(
                "Summary generation failed for source_notice_id=%s; using fallback",
                notice.source_notice_id,
            )
            return self._fallback_summary(notice)
