# app/core/database.py
from collections.abc import AsyncGenerator
import logging
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Engine configuration with asyncpg connection pooling
engine: AsyncEngine = create_async_engine(
    url=str(settings.DATABASE_URL),
    echo=settings.DEBUG and settings.ENVIRONMENT == "development",
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,
)

# Async session factory
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def dispose_database_engine() -> None:
    """Disposes the SQLAlchemy engine connections during application shutdown."""
    logger.info("Closing active database connection pools...")
    await engine.dispose()
    logger.info("Database connection pools closed successfully.")


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Direct session dependency for lightweight query operations."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


DatabaseSessionDep = Annotated[AsyncSession, Depends(get_db_session)]