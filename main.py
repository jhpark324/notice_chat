import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from notice_chat.db import close_db, init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Application startup: initializing database")
    await init_db()
    logger.info("Application startup complete")
    try:
        yield
    finally:
        logger.info("Application shutdown: closing database engine")
        await close_db()
        logger.info("Application shutdown complete")


def create_app(*, enable_lifespan: bool = True) -> FastAPI:
    app = FastAPI(lifespan=lifespan if enable_lifespan else None)
    return app


app = create_app()
