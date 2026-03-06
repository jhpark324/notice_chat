from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SkuNoticeBase(BaseModel):
    """서경대 공지 스키마 공통 베이스."""

    model_config = ConfigDict(extra="forbid")


class SkuNoticeRequiredFields(SkuNoticeBase):
    """생성/조회에 공통으로 필요한 필드."""

    source_notice_id: int = Field(..., ge=1, description="학교 공지 원본 ID")
    detail_url: str = Field(..., max_length=500, description="공지 상세 페이지 URL")
    title: str = Field(..., max_length=500, description="공지 제목")
    category: str = Field(
        ..., max_length=50, description="공지 분류(학사/장학/일반 등)"
    )
    author_org: str | None = Field(
        default=None, max_length=100, description="작성 부서 또는 작성자"
    )
    posted_date: date | None = Field(default=None, description="공지 게시일")
    status: str | None = Field(
        default=None, max_length=20, description="진행 상태(진행중/진행완료/없음)"
    )
    list_number: int | None = Field(default=None, description="목록 번호")
    period_start: date | None = Field(default=None, description="접수/운영 시작일")
    period_end: date | None = Field(default=None, description="접수/운영 종료일")
    summary_text: str = Field(..., description="공지 요약 텍스트")
    attachments: list[dict[str, Any]] | None = Field(
        default=None,
        description="첨부파일 목록(JSON)",
    )


class SkuNoticeCreate(SkuNoticeRequiredFields):
    """공지 생성/업서트 입력 스키마."""


class SkuNoticeUpdate(SkuNoticeBase):
    """공지 부분 수정 입력 스키마."""

    source_notice_id: int | None = Field(
        default=None, ge=1, description="학교 공지 원본 ID"
    )
    detail_url: str | None = Field(
        default=None, max_length=500, description="공지 상세 페이지 URL"
    )
    title: str | None = Field(default=None, max_length=500, description="공지 제목")
    category: str | None = Field(
        default=None, max_length=50, description="공지 분류(학사/장학/일반 등)"
    )
    author_org: str | None = Field(
        default=None, max_length=100, description="작성 부서 또는 작성자"
    )
    posted_date: date | None = Field(default=None, description="공지 게시일")
    status: str | None = Field(
        default=None, max_length=20, description="진행 상태(진행중/진행완료/없음)"
    )
    list_number: int | None = Field(default=None, description="목록 번호")
    period_start: date | None = Field(default=None, description="접수/운영 시작일")
    period_end: date | None = Field(default=None, description="접수/운영 종료일")
    summary_text: str | None = Field(default=None, description="공지 요약 텍스트")
    attachments: list[dict[str, Any]] | None = Field(
        default=None, description="첨부파일 목록(JSON)"
    )


class SkuNoticeRead(SkuNoticeRequiredFields):
    """공지 조회 응답 스키마."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int = Field(..., description="내부 PK")
    created_at: datetime = Field(..., description="레코드 생성 시각")
    updated_at: datetime = Field(..., description="레코드 최종 수정 시각")
