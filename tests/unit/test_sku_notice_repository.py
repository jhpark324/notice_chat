from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from notice_chat.models import DBSkuNotice
from notice_chat.repositories import SkuNoticeRepository
from notice_chat.schemas import SkuNoticeCreate, SkuNoticeUpdate

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.fixture
def session_mock() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def create_payload() -> SkuNoticeCreate:
    return SkuNoticeCreate(
        source_notice_id=61447,
        detail_url="https://www.skuniv.ac.kr/notice/61447",
        title="2026 scholarship notice",
        category="scholarship",
        author_org="student office",
        posted_date=date(2026, 3, 5),
        status="ongoing",
        list_number=1,
        period_start=date(2026, 3, 5),
        period_end=date(2026, 3, 20),
        summary_text="notice summary",
        attachments=[
            {"file_name": "apply.hwp", "file_url": "https://files.example/a.hwp"}
        ],
    )


def _build_notice() -> DBSkuNotice:
    return DBSkuNotice(
        id=10,
        source_notice_id=61447,
        detail_url="https://www.skuniv.ac.kr/notice/61447",
        title="original title",
        category="scholarship",
        author_org="student office",
        posted_date=date(2026, 3, 5),
        status="ongoing",
        list_number=1,
        period_start=date(2026, 3, 5),
        period_end=date(2026, 3, 20),
        summary_text="original summary",
        attachments=[
            {"file_name": "old.hwp", "file_url": "https://files.example/old.hwp"}
        ],
    )


async def test_get_by_id_returns_notice(session_mock: AsyncMock) -> None:
    repo = SkuNoticeRepository(session=session_mock)
    expected = _build_notice()
    session_mock.scalar.return_value = expected

    result = await repo.get_by_id(10)

    assert result is expected
    session_mock.scalar.assert_awaited_once()


async def test_list_returns_filtered_notice_list(session_mock: AsyncMock) -> None:
    repo = SkuNoticeRepository(session=session_mock)
    notices = [_build_notice()]

    scalar_result = MagicMock()
    scalar_result.all.return_value = notices
    session_mock.scalars.return_value = scalar_result

    result = await repo.list(
        limit=10,
        offset=0,
        category="scholarship",
        status="ongoing",
    )

    assert result == notices
    session_mock.scalars.assert_awaited_once()
    scalar_result.all.assert_called_once()


async def test_search_text_tokenizes_multi_word_query(session_mock: AsyncMock) -> None:
    repo = SkuNoticeRepository(session=session_mock)

    scalar_result = MagicMock()
    scalar_result.all.return_value = []
    session_mock.scalars.return_value = scalar_result

    await repo.search_text(query="장학금 신청", limit=20)

    stmt = session_mock.scalars.await_args.args[0]
    compiled = stmt.compile()
    pattern_values = [
        value
        for value in compiled.params.values()
        if isinstance(value, str) and value.startswith("%") and value.endswith("%")
    ]

    assert pattern_values.count("%장학금%") == 2
    assert pattern_values.count("%신청%") == 2
    assert "%장학금 신청%" not in pattern_values


async def test_create_adds_and_commits_notice(
    session_mock: AsyncMock,
    create_payload: SkuNoticeCreate,
) -> None:
    repo = SkuNoticeRepository(session=session_mock)

    result = await repo.create(create_payload)

    session_mock.add.assert_called_once()
    session_mock.commit.assert_awaited_once()
    session_mock.refresh.assert_awaited_once_with(result)
    assert result.title == create_payload.title
    assert result.source_notice_id == create_payload.source_notice_id


async def test_update_by_source_notice_id_returns_none_when_notice_missing(
    session_mock: AsyncMock,
) -> None:
    repo = SkuNoticeRepository(session=session_mock)
    repo.get_by_source_notice_id = AsyncMock(return_value=None)  # type: ignore[method-assign]

    result = await repo.update_by_source_notice_id(
        source_notice_id=99999,
        payload=SkuNoticeUpdate(title="updated"),
    )

    assert result is None
    session_mock.add.assert_not_called()
    session_mock.commit.assert_not_awaited()
    session_mock.refresh.assert_not_awaited()


async def test_update_by_source_notice_id_updates_only_given_fields(
    session_mock: AsyncMock,
) -> None:
    repo = SkuNoticeRepository(session=session_mock)
    existing = _build_notice()
    original_summary = existing.summary_text
    repo.get_by_source_notice_id = AsyncMock(return_value=existing)  # type: ignore[method-assign]

    result = await repo.update_by_source_notice_id(
        source_notice_id=existing.source_notice_id,
        payload=SkuNoticeUpdate(title="updated title", status="done"),
    )

    assert result is existing
    assert existing.title == "updated title"
    assert existing.status == "done"
    assert existing.summary_text == original_summary
    session_mock.add.assert_called_once_with(existing)
    session_mock.commit.assert_awaited_once()
    session_mock.refresh.assert_awaited_once_with(existing)


async def test_upsert_creates_when_notice_not_exists(
    session_mock: AsyncMock,
    create_payload: SkuNoticeCreate,
) -> None:
    repo = SkuNoticeRepository(session=session_mock)
    created_notice = _build_notice()
    repo.get_by_source_notice_id = AsyncMock(return_value=None)  # type: ignore[method-assign]
    repo.create = AsyncMock(return_value=created_notice)  # type: ignore[method-assign]

    result = await repo.upsert_by_source_notice_id(create_payload)

    assert result is created_notice
    repo.create.assert_awaited_once_with(create_payload)


async def test_upsert_updates_when_notice_exists(
    session_mock: AsyncMock,
    create_payload: SkuNoticeCreate,
) -> None:
    repo = SkuNoticeRepository(session=session_mock)
    existing = _build_notice()
    repo.get_by_source_notice_id = AsyncMock(return_value=existing)  # type: ignore[method-assign]

    result = await repo.upsert_by_source_notice_id(create_payload)

    assert result is existing
    assert existing.title == create_payload.title
    assert existing.summary_text == create_payload.summary_text
    assert existing.attachments == create_payload.attachments
    session_mock.add.assert_called_once_with(existing)
    session_mock.commit.assert_awaited_once()
    session_mock.refresh.assert_awaited_once_with(existing)


async def test_delete_by_source_notice_id_returns_false_when_missing(
    session_mock: AsyncMock,
) -> None:
    repo = SkuNoticeRepository(session=session_mock)
    repo.get_by_source_notice_id = AsyncMock(return_value=None)  # type: ignore[method-assign]

    result = await repo.delete_by_source_notice_id(99999)

    assert result is False
    session_mock.delete.assert_not_awaited()
    session_mock.commit.assert_not_awaited()


async def test_delete_by_source_notice_id_deletes_notice_when_exists(
    session_mock: AsyncMock,
) -> None:
    repo = SkuNoticeRepository(session=session_mock)
    existing = _build_notice()
    repo.get_by_source_notice_id = AsyncMock(return_value=existing)  # type: ignore[method-assign]

    result = await repo.delete_by_source_notice_id(existing.source_notice_id)

    assert result is True
    session_mock.delete.assert_awaited_once_with(existing)
    session_mock.commit.assert_awaited_once()
