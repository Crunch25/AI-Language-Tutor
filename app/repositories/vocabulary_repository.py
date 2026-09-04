from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import VocabularyMemory
from app.repositories.base import BaseRepository


class VocabularyRepository(BaseRepository[VocabularyMemory]):
    """Repository managing user vocabulary items, vector similarity matching, and SRS tracking."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(VocabularyMemory, session)

    async def search_similar_vocabulary(
        self,
        user_id: UUID,
        target_language: str,
        embedding: list[float],
        limit: int = 5,
        max_distance: float = 0.45,
    ) -> list[tuple[VocabularyMemory, float]]:
        """
        Performs approximate nearest neighbor (ANN) search over pgvector HNSW index
        using cosine distance: (1 - cosine_similarity).
        
        Returns pairs of (VocabularyMemory, cosine_similarity_score).
        """
        # Distance calculation: 0 = identical, 2 = opposite
        distance_expr = VocabularyMemory.embedding.cosine_distance(embedding)

        stmt = (
            select(VocabularyMemory, distance_expr.label("distance"))
            .where(
                VocabularyMemory.user_id == user_id,
                VocabularyMemory.language == target_language,
                distance_expr <= max_distance,
            )
            .order_by(distance_expr.asc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        matches: list[tuple[VocabularyMemory, float]] = []

        for row in result.all():
            entity: VocabularyMemory = row[0]
            distance: float = float(row[1])
            similarity = max(0.0, min(1.0, 1.0 - distance))
            matches.append((entity, round(similarity, 4)))

        return matches

    async def get_due_srs_items(
        self,
        user_id: UUID,
        target_language: str | None = None,
        limit: int = 30,
        before_timestamp: datetime | None = None,
    ) -> Sequence[VocabularyMemory]:
        """Fetches pending spaced-repetition cards scheduled for review at or before current time."""
        if before_timestamp is None:
            before_timestamp = datetime.now(timezone.utc)

        filters = [
            VocabularyMemory.user_id == user_id,
            VocabularyMemory.next_review_at <= before_timestamp,
        ]
        if target_language is not None:
            filters.append(VocabularyMemory.language == target_language)

        stmt = (
            select(VocabularyMemory)
            .where(*filters)
            .order_by(VocabularyMemory.next_review_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_word(
        self,
        user_id: UUID,
        language: str,
        word: str,
    ) -> VocabularyMemory | None:
        """Finds existing vocabulary entry by direct case-insensitive term match."""
        stmt = select(VocabularyMemory).where(
            VocabularyMemory.user_id == user_id,
            VocabularyMemory.language == language,
            VocabularyMemory.word.ilike(word.strip()),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()