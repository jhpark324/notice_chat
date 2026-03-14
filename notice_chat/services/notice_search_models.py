from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from notice_chat.models import DBSkuNotice

SearchMode = Literal["sql_only", "semantic_only", "hybrid"]


@dataclass(slots=True)
class NoticeSearchFilters:
    category: str | None = None
    author_org: str | None = None
    posted_from: date | None = None
    posted_to: date | None = None
    status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "author_org": self.author_org,
            "posted_from": self.posted_from,
            "posted_to": self.posted_to,
            "status": self.status,
        }


@dataclass(slots=True)
class NoticeSearchResultItem:
    id: int
    source_notice_id: int
    title: str
    category: str
    author_org: str | None
    posted_date: date | None
    status: str | None
    detail_url: str
    summary_text: str
    score: float = 0.0
    keyword_score: float = 0.0
    semantic_score: float = 0.0
    recency_score: float = 0.0
    match_reason: list[str] = field(default_factory=list)

    @classmethod
    def from_db(cls, notice: DBSkuNotice) -> "NoticeSearchResultItem":
        return cls(
            id=notice.id,
            source_notice_id=notice.source_notice_id,
            title=notice.title,
            category=notice.category,
            author_org=notice.author_org,
            posted_date=notice.posted_date,
            status=notice.status,
            detail_url=notice.detail_url,
            summary_text=notice.summary_text or "",
        )


@dataclass(slots=True)
class NoticeSearchResponse:
    query: str
    applied_filters: dict[str, Any]
    mode: SearchMode
    results: list[NoticeSearchResultItem]
    total_returned: int
    errors: list[str] = field(default_factory=list)
