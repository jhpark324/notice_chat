from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import (
    BigInteger,
    Date,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class DBSkuNotice(BaseModel):
    """Seokyeong University notice model."""

    __tablename__ = "sku_notices"
    __table_args__ = (
        UniqueConstraint("source_notice_id", name="uq_sku_notices_source_notice_id"),
        Index("ix_sku_notices_posted_date", "posted_date"),
        Index("ix_sku_notices_category", "category"),
        Index("ix_sku_notices_status", "status"),
    )

    source_notice_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="학교 공지 원본 ID (상세 URL의 숫자)",
    )
    detail_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="공지 상세 페이지 URL",
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="공지 제목",
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="공지 분류(학사/장학/일반 등)",
    )
    author_org: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="작성 부서 또는 작성자",
    )
    posted_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="공지 게시일",
    )
    status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="진행 상태(진행중/진행완료/없음)",
    )
    list_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="목록 번호(고정 공지 등은 비어 있을 수 있음)",
    )
    period_start: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="접수/운영 시작일",
    )
    period_end: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="접수/운영 종료일",
    )
    summary_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=False,
        comment="공지 요약 텍스트",
    )
    attachments: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="첨부파일 목록(JSON)",
    )
