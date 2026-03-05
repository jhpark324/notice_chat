from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from notice_chat.models import DBSkuNotice
from notice_chat.repositories import SkuNoticeRepository
from notice_chat.schemas import SkuNoticeCreate, SkuNoticeUpdate

pytestmark = pytest.mark.unit


@pytest.fixture
def session_mock() -> MagicMock:
    return MagicMock(spec=Session)


@pytest.fixture
def create_payload() -> SkuNoticeCreate:
    return SkuNoticeCreate(
        source_notice_id=61447,
        detail_url="https://www.skuniv.ac.kr/notice/61447",
        title="2026학년도 장학 공지",
        category="장학",
        author_org="학생처",
        posted_date=date(2026, 3, 5),
        status="진행중",
        list_number=1,
        period_start=date(2026, 3, 5),
        period_end=date(2026, 3, 20),
        summary_text="장학 신청 공지 요약",
        attachments=[{"file_name": "신청서.hwp", "file_url": "https://files.example/a.hwp"}],
    )


def _build_notice() -> DBSkuNotice:
    return DBSkuNotice(
        id=10,
        source_notice_id=61447,
        detail_url="https://www.skuniv.ac.kr/notice/61447",
        title="기존 제목",
        category="장학",
        author_org="학생처",
        posted_date=date(2026, 3, 5),
        status="진행중",
        list_number=1,
        period_start=date(2026, 3, 5),
        period_end=date(2026, 3, 20),
        summary_text="기존 요약",
        attachments=[{"file_name": "old.hwp", "file_url": "https://files.example/old.hwp"}],
    )


def test_get_by_id_returns_notice(session_mock: MagicMock) -> None:
    repo = SkuNoticeRepository(session=session_mock)
    expected = _build_notice()
    session_mock.scalar.return_value = expected

    result = repo.get_by_id(10)

    assert result is expected
    session_mock.scalar.assert_called_once()


def test_list_returns_filtered_notice_list(session_mock: MagicMock) -> None:
    repo = SkuNoticeRepository(session=session_mock)
    notices = [_build_notice()]

    scalar_result = MagicMock()
    scalar_result.all.return_value = notices
    session_mock.scalars.return_value = scalar_result

    result = repo.list(limit=10, offset=0, category="장학", status="진행중")

    assert result == notices
    session_mock.scalars.assert_called_once()
    scalar_result.all.assert_called_once()


def test_create_adds_and_commits_notice(
    session_mock: MagicMock,
    create_payload: SkuNoticeCreate,
) -> None:
    repo = SkuNoticeRepository(session=session_mock)

    result = repo.create(create_payload)

    session_mock.add.assert_called_once()
    session_mock.commit.assert_called_once()
    session_mock.refresh.assert_called_once_with(result)
    assert result.title == create_payload.title
    assert result.source_notice_id == create_payload.source_notice_id


def test_update_by_source_notice_id_returns_none_when_notice_missing(
    session_mock: MagicMock,
) -> None:
    repo = SkuNoticeRepository(session=session_mock)
    repo.get_by_source_notice_id = MagicMock(return_value=None)  # type: ignore[method-assign]

    result = repo.update_by_source_notice_id(
        source_notice_id=99999,
        payload=SkuNoticeUpdate(title="수정"),
    )

    assert result is None
    session_mock.add.assert_not_called()
    session_mock.commit.assert_not_called()
    session_mock.refresh.assert_not_called()


def test_update_by_source_notice_id_updates_only_given_fields(
    session_mock: MagicMock,
) -> None:
    repo = SkuNoticeRepository(session=session_mock)
    existing = _build_notice()
    original_summary = existing.summary_text
    repo.get_by_source_notice_id = MagicMock(return_value=existing)  # type: ignore[method-assign]

    result = repo.update_by_source_notice_id(
        source_notice_id=existing.source_notice_id,
        payload=SkuNoticeUpdate(title="수정된 제목", status="진행완료"),
    )

    assert result is existing
    assert existing.title == "수정된 제목"
    assert existing.status == "진행완료"
    assert existing.summary_text == original_summary
    session_mock.add.assert_called_once_with(existing)
    session_mock.commit.assert_called_once()
    session_mock.refresh.assert_called_once_with(existing)


def test_upsert_creates_when_notice_not_exists(
    session_mock: MagicMock,
    create_payload: SkuNoticeCreate,
) -> None:
    repo = SkuNoticeRepository(session=session_mock)
    created_notice = _build_notice()
    repo.get_by_source_notice_id = MagicMock(return_value=None)  # type: ignore[method-assign]
    repo.create = MagicMock(return_value=created_notice)  # type: ignore[method-assign]

    result = repo.upsert_by_source_notice_id(create_payload)

    assert result is created_notice
    repo.create.assert_called_once_with(create_payload)


def test_upsert_updates_when_notice_exists(
    session_mock: MagicMock,
    create_payload: SkuNoticeCreate,
) -> None:
    repo = SkuNoticeRepository(session=session_mock)
    existing = _build_notice()
    repo.get_by_source_notice_id = MagicMock(return_value=existing)  # type: ignore[method-assign]

    result = repo.upsert_by_source_notice_id(create_payload)

    assert result is existing
    assert existing.title == create_payload.title
    assert existing.summary_text == create_payload.summary_text
    assert existing.attachments == create_payload.attachments
    session_mock.add.assert_called_once_with(existing)
    session_mock.commit.assert_called_once()
    session_mock.refresh.assert_called_once_with(existing)


def test_delete_by_source_notice_id_returns_false_when_missing(
    session_mock: MagicMock,
) -> None:
    repo = SkuNoticeRepository(session=session_mock)
    repo.get_by_source_notice_id = MagicMock(return_value=None)  # type: ignore[method-assign]

    result = repo.delete_by_source_notice_id(99999)

    assert result is False
    session_mock.delete.assert_not_called()
    session_mock.commit.assert_not_called()


def test_delete_by_source_notice_id_deletes_notice_when_exists(
    session_mock: MagicMock,
) -> None:
    repo = SkuNoticeRepository(session=session_mock)
    existing = _build_notice()
    repo.get_by_source_notice_id = MagicMock(return_value=existing)  # type: ignore[method-assign]

    result = repo.delete_by_source_notice_id(existing.source_notice_id)

    assert result is True
    session_mock.delete.assert_called_once_with(existing)
    session_mock.commit.assert_called_once()
