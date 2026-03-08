from __future__ import annotations

from datetime import date

import pytest

from notice_chat.services import CrawledNotice, LangChainNoticeEmbeddingService

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _build_notice() -> CrawledNotice:
    return CrawledNotice(
        source_notice_id=61471,
        detail_url="https://www.skuniv.ac.kr/notice/61471",
        title="2026 장학금 신청 안내",
        category="장학",
        author_org="학생처",
        posted_date=date(2026, 3, 8),
        status="진행중",
        list_number=1,
        period_start=date(2026, 3, 8),
        period_end=date(2026, 3, 20),
        raw_text="신청 대상은 재학생이며 신청 기간 내 제출 바랍니다.",
        image_urls=[],
        attachments=[],
    )


async def test_embed_notice_returns_none_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    service = LangChainNoticeEmbeddingService()

    result = await service.embed_notice(_build_notice(), summary_text="요약")

    assert result is None


async def test_embed_notice_uses_injected_client() -> None:
    class _FakeEmbeddings:
        def __init__(self) -> None:
            self.last_text: str | None = None

        async def aembed_query(self, text: str) -> list[float]:
            self.last_text = text
            return [0.1, 0.2, 0.3]

    fake = _FakeEmbeddings()
    service = LangChainNoticeEmbeddingService(embedding_client=fake)

    result = await service.embed_notice(_build_notice(), summary_text="요약 텍스트")

    assert result == [0.1, 0.2, 0.3]
    assert fake.last_text is not None
    assert "[요약]" in fake.last_text
