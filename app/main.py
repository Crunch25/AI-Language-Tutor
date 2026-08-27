# app/main.py
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from fastapi import FastAPI

from app.core.database import dispose_database_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup tasks: Initialize vector indexes, verify AI API connectivity
    yield
    # Shutdown tasks: Drain and cleanly terminate asyncpg pool
    await dispose_database_engine()


app = FastAPI(lifespan=lifespan)