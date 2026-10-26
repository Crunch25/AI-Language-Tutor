from collections.abc import Sequence
from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import BaseUUIDModel

ModelType = TypeVar("ModelType", bound=BaseUUIDModel)


class BaseRepository(Generic[ModelType]):
    """Generic async repository providing baseline CRUD operations."""

    def __init__(self, model: type[ModelType], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get(self, entity_id: UUID) -> ModelType | None:
        """Fetch a single entity by its primary key ID."""
        return await self.session.get(self.model, entity_id)

    async def list(
        self,
        offset: int = 0,
        limit: int = 100,
        **filters: Any,
    ) -> Sequence[ModelType]:
        """Fetch a paginated list of entities matching optional equality filters."""
        stmt = select(self.model).filter_by(**filters).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def add(self, entity: ModelType) -> ModelType:
        """Add an entity to the active session."""
        self.session.add(entity)
        return entity

    async def add_all(self, entities: Sequence[ModelType]) -> Sequence[ModelType]:
        """Add multiple entities to the active session."""
        self.session.add_all(entities)
        return entities

    async def delete(self, entity_id: UUID) -> bool:
        """Delete an entity by ID. Returns True if row was deleted, False otherwise."""
        stmt = delete(self.model).where(self.model.id == entity_id)
        result = await self.session.execute(stmt)
        return (result.rowcount or 0) > 0