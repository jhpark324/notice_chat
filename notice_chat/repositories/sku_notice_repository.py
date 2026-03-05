from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from notice_chat.models import DBSkuNotice
from notice_chat.schemas import SkuNoticeCreate, SkuNoticeUpdate


class SkuNoticeRepository:
    """Repository for sku notice persistence operations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, notice_id: int) -> DBSkuNotice | None:
        stmt = select(DBSkuNotice).where(DBSkuNotice.id == notice_id)
        return self.session.scalar(stmt)

    def get_by_source_notice_id(self, source_notice_id: int) -> DBSkuNotice | None:
        stmt = select(DBSkuNotice).where(
            DBSkuNotice.source_notice_id == source_notice_id
        )
        return self.session.scalar(stmt)

    def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        category: str | None = None,
        status: str | None = None,
    ) -> Sequence[DBSkuNotice]:
        stmt: Select[tuple[DBSkuNotice]] = select(DBSkuNotice).order_by(
            DBSkuNotice.posted_date.desc(), DBSkuNotice.id.desc()
        )
        if category is not None:
            stmt = stmt.where(DBSkuNotice.category == category)
        if status is not None:
            stmt = stmt.where(DBSkuNotice.status == status)
        stmt = stmt.offset(offset).limit(limit)
        return self.session.scalars(stmt).all()

    def create(self, payload: SkuNoticeCreate) -> DBSkuNotice:
        notice = DBSkuNotice(**payload.model_dump())
        self.session.add(notice)
        self.session.commit()
        self.session.refresh(notice)
        return notice

    def update_by_source_notice_id(
        self,
        source_notice_id: int,
        payload: SkuNoticeUpdate,
    ) -> DBSkuNotice | None:
        notice = self.get_by_source_notice_id(source_notice_id)
        if notice is None:
            return None

        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            return notice

        for field, value in update_data.items():
            setattr(notice, field, value)

        self.session.add(notice)
        self.session.commit()
        self.session.refresh(notice)
        return notice

    def upsert_by_source_notice_id(self, payload: SkuNoticeCreate) -> DBSkuNotice:
        notice = self.get_by_source_notice_id(payload.source_notice_id)
        if notice is None:
            return self.create(payload)

        update_data = payload.model_dump()
        for field, value in update_data.items():
            setattr(notice, field, value)

        self.session.add(notice)
        self.session.commit()
        self.session.refresh(notice)
        return notice

    def delete_by_source_notice_id(self, source_notice_id: int) -> bool:
        notice = self.get_by_source_notice_id(source_notice_id)
        if notice is None:
            return False

        self.session.delete(notice)
        self.session.commit()
        return True
