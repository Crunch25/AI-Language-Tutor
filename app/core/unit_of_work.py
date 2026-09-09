# app/core/unit_of_work.py
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from types import TracebackType
from typing import Annotated, Self

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import async_session_factory
from app.repositories.chat_repository import ChatRepository
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository
from app.repositories.vocabulary_repository import VocabularyRepository


class IUnitOfWork(ABC):
    """Abstract Base Class defining the Unit of Work interface."""

    chat: ChatRepository
    vocabulary: VocabularyRepository
    user_repo: UserRepository
    token_repo: TokenRepository

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()

    @abstractmethod
    async def commit(self) -> None:
        """Commit pending changes to the storage layer."""
        raise NotImplementedError

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the active transaction."""
        raise NotImplementedError


class SqlAlchemyUnitOfWork(IUnitOfWork):
    """Concrete implementation of Unit of Work for SQLAlchemy 2.0."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
    ) -> None:
        self._session_factory = session_factory
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> Self:
        self.session = self._session_factory()
        
        self.chat = ChatRepository(self.session)
        self.vocabulary = VocabularyRepository(self.session)
        self.user_repo = UserRepository(self.session)
        self.token_repo = TokenRepository(self.session)
        
        return await super().__aenter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            await super().__aexit__(exc_type, exc_val, exc_tb)
        finally:
            if self.session is not None:
                await self.session.close()

    async def commit(self) -> None:
        if self.session is not None:
            await self.session.commit()

    async def rollback(self) -> None:
        if self.session is not None:
            await self.session.rollback()


async def get_unit_of_work() -> AsyncGenerator[IUnitOfWork]:
    """FastAPI dependency yielding an instantiated Unit of Work per request."""
    uow = SqlAlchemyUnitOfWork()
    async with uow:
        yield uow


UnitOfWorkDep = Annotated[IUnitOfWork, Depends(get_unit_of_work)]
UOWDep = UnitOfWorkDep