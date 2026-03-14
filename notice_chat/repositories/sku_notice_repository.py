from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from notice_chat.models import DBSkuNotice
from notice_chat.schemas import SkuNoticeCreate, SkuNoticeUpdate


class SkuNoticeRepository:
    """Repository for sku notice persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, notice_id: int) -> DBSkuNotice | None:
        stmt = select(DBSkuNotice).where(DBSkuNotice.id == notice_id)
        return await self.session.scalar(stmt)

    async def get_by_source_notice_id(
        self, source_notice_id: int
    ) -> DBSkuNotice | None:
        stmt = select(DBSkuNotice).where(
            DBSkuNotice.source_notice_id == source_notice_id
        )
        return await self.session.scalar(stmt)

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        category: str | None = None,
        status: str | None = None,
    ) -> Sequence[DBSkuNotice]:
        stmt = select(DBSkuNotice).order_by(
            DBSkuNotice.posted_date.desc(), DBSkuNotice.id.desc()
        )
        if category is not None:
            stmt = stmt.where(DBSkuNotice.category == category)
        if status is not None:
            stmt = stmt.where(DBSkuNotice.status == status)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def search_text(
        self,
        *,
        query: str,
        limit: int = 20,
        category: str | None = None,
        author_org: str | None = None,
        posted_from: date | None = None,
        posted_to: date | None = None,
        status: str | None = None,
    ) -> Sequence[DBSkuNotice]:
        stmt = select(DBSkuNotice)

        tokens: list[str] = []
        for raw_token in query.strip().split():
            token = raw_token.strip()
            if token and token not in tokens:
                tokens.append(token)

        for token in tokens:
            pattern = f"%{token}%"
            stmt = stmt.where(
                or_(
                    DBSkuNotice.title.ilike(pattern),
                    DBSkuNotice.summary_text.ilike(pattern),
                )
            )

        if category is not None:
            stmt = stmt.where(DBSkuNotice.category == category)
        if author_org is not None:
            stmt = stmt.where(DBSkuNotice.author_org == author_org)
        if posted_from is not None:
            stmt = stmt.where(DBSkuNotice.posted_date >= posted_from)
        if posted_to is not None:
            stmt = stmt.where(DBSkuNotice.posted_date <= posted_to)
        if status is not None:
            stmt = stmt.where(DBSkuNotice.status == status)

        stmt = stmt.order_by(DBSkuNotice.posted_date.desc(), DBSkuNotice.id.desc()).limit(
            limit
        )
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def list_semantic_candidates(
        self,
        *,
        limit: int = 200,
        category: str | None = None,
        author_org: str | None = None,
        posted_from: date | None = None,
        posted_to: date | None = None,
        status: str | None = None,
    ) -> Sequence[DBSkuNotice]:
        stmt = select(DBSkuNotice).where(DBSkuNotice.embedding.is_not(None))

        if category is not None:
            stmt = stmt.where(DBSkuNotice.category == category)
        if author_org is not None:
            stmt = stmt.where(DBSkuNotice.author_org == author_org)
        if posted_from is not None:
            stmt = stmt.where(DBSkuNotice.posted_date >= posted_from)
        if posted_to is not None:
            stmt = stmt.where(DBSkuNotice.posted_date <= posted_to)
        if status is not None:
            stmt = stmt.where(DBSkuNotice.status == status)

        stmt = stmt.order_by(DBSkuNotice.posted_date.desc(), DBSkuNotice.id.desc()).limit(
            limit
        )
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def create(self, payload: SkuNoticeCreate) -> DBSkuNotice:
        notice = DBSkuNotice(**payload.model_dump())
        self.session.add(notice)
        await self.session.commit()
        await self.session.refresh(notice)
        return notice

    async def update_by_source_notice_id(
        self,
        source_notice_id: int,
        payload: SkuNoticeUpdate,
    ) -> DBSkuNotice | None:
        notice = await self.get_by_source_notice_id(source_notice_id)
        if notice is None:
            return None

        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            return notice

        for field, value in update_data.items():
            setattr(notice, field, value)

        self.session.add(notice)
        await self.session.commit()
        await self.session.refresh(notice)
        return notice

    async def upsert_by_source_notice_id(
        self, payload: SkuNoticeCreate
    ) -> DBSkuNotice:
        notice = await self.get_by_source_notice_id(payload.source_notice_id)
        if notice is None:
            return await self.create(payload)

        update_data = payload.model_dump()
        for field, value in update_data.items():
            setattr(notice, field, value)

        self.session.add(notice)
        await self.session.commit()
        await self.session.refresh(notice)
        return notice

    async def delete_by_source_notice_id(self, source_notice_id: int) -> bool:
        notice = await self.get_by_source_notice_id(source_notice_id)
        if notice is None:
            return False

        await self.session.delete(notice)
        await self.session.commit()
        return True
