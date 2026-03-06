from contextlib import asynccontextmanager

from fastapi import FastAPI

from notice_chat.db import close_db, init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    try:
        yield
    finally:
        await close_db()


app = FastAPI(lifespan=lifespan)
