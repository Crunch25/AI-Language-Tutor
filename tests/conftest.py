from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.v1.endpoints.chat import get_current_user
from app.core.config import get_settings
from app.core.database import Base
from app.core.unit_of_work import IUnitOfWork, SqlAlchemyUnitOfWork, get_unit_of_work
from app.main import app
from app.models.chat import CEFRLevel, ChatSession
from app.models.user import User

settings = get_settings()

# Use dedicated test DB (or test schema) with pgvector enabled
TEST_DB_URL = str(settings.DATABASE_URL)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        # Enable pgvector extension before creating tables
        await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector;")
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provides an isolated session using a non-committing transaction savepoint.
    Everything done in the test is rolled back cleanly.
    """
    connection = await test_engine.connect()
    trans = await connection.begin()
    session_factory = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    session = session_factory()

    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await connection.close()


@pytest.fixture
def mock_user() -> User:
    user = User(
        email="test_learner@example.com",
        hashed_password="hashed_test_password",
        full_name="Test Student",
        is_active=True,
    )
    user.id = UUID("11111111-1111-1111-1111-111111111111")
    return user


class TestUnitOfWork(SqlAlchemyUnitOfWork):
    """UoW bound to the test session that rolls back rather than committing to disk."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self.session = session

    async def __aenter__(self) -> "TestUnitOfWork":
        # Wire up repositories against the active transaction
        from app.repositories.chat_repository import ChatRepository
        from app.repositories.vocabulary_repository import VocabularyRepository

        self.chat = ChatRepository(self.session)
        self.vocabulary = VocabularyRepository(self.session)
        return self

    async def commit(self) -> None:
        # Flush pending changes to ensure constraints and foreign keys validate
        # without committing the outer test transaction
        await self.session.flush()

    async def rollback(self) -> None:
        await self.session.rollback()


@pytest.fixture
async def mock_llm_stream():
    """Mocks OpenAI embedding creation and streaming completion iterators."""
    async def mock_embedding(*args: Any, **kwargs: Any):
        mock_resp = AsyncMock()
        mock_data = AsyncMock()
        mock_data.embedding = [0.01] * 1536
        mock_resp.data = [mock_data]
        return mock_resp

    async def mock_completion_stream(*args: Any, **kwargs: Any):
        chunks = ["¡Hola! ", "¿Cómo ", "estás ", "hoy?"]
        for c in chunks:
            mock_chunk = AsyncMock()
            mock_choice = AsyncMock()
            mock_choice.delta.content = c
            mock_chunk.choices = [mock_choice]
            yield mock_chunk

    with (
        patch("app.services.ai_tutor_service.client.embeddings.create", side_effect=mock_embedding),
        patch("app.services.ai_tutor_service.client.chat.completions.create", side_effect=mock_completion_stream),
        patch("app.services.ai_tutor_service.create_pool", new_callable=AsyncMock) as mock_redis,
    ):
        # Mock Redis queue enqueue
        mock_pool = AsyncMock()
        mock_redis.return_value = mock_pool
        yield


@pytest.fixture
async def async_client(
    db_session: AsyncSession,
    mock_user: User,
) -> AsyncGenerator[AsyncClient, None]:
    """Provides an authenticated AsyncClient with dependencies overridden."""

    async def override_get_uow() -> AsyncGenerator[IUnitOfWork, None]:
        uow = TestUnitOfWork(db_session)
        async with uow:
            yield uow

    async def override_get_current_user() -> User:
        return mock_user

    app.dependency_overrides[get_unit_of_work] = override_get_uow
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()