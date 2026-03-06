from __future__ import annotations

from pathlib import Path

from notice_chat.models import Base

from .settings import DATABASE_SETTINGS
from .session import engine


def _ensure_sqlite_directory() -> None:
    prefix = "sqlite+aiosqlite:///"
    database_url = DATABASE_SETTINGS.url

    if not database_url.startswith(prefix):
        return

    raw_path = database_url[len(prefix) :]
    if raw_path in {"", ":memory:"}:
        return

    Path(raw_path).parent.mkdir(parents=True, exist_ok=True)


async def init_db() -> None:
    _ensure_sqlite_directory()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    await engine.dispose()
