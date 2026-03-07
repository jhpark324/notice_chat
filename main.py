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


app = FastAPI(lifespan=lifespan)
