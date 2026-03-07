from __future__ import annotations

import logging

from sqlalchemy import text

from .session import engine

logger = logging.getLogger(__name__)


async def init_db() -> None:
    # Keep startup lightweight: verify DB connectivity only.
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connectivity check passed")
    except Exception:
        logger.exception("Database initialization failed")
        raise


async def close_db() -> None:
    await engine.dispose()
    logger.info("Database engine disposed")
