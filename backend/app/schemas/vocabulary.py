from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VocabularyCreate(BaseModel):
    language: str = Field(..., min_length=2, max_length=50)
    word: str = Field(..., min_length=1, max_length=100)
    translation: str = Field(..., min_length=1, max_length=255)
    context_sentence: str | None = None


class SRSReviewUpdate(BaseModel):
    """
    SuperMemo-2 review grade:
    5 - perfect response
    4 - correct response after a hesitation
    3 - correct response recalled with serious difficulty
    2 - incorrect response; where the correct one seemed easy to recall
    1 - incorrect response; the correct one remembered
    0 - complete blackout
    """
    quality_score: int = Field(..., ge=0, le=5, description="SM-2 quality grade from 0 to 5")


class VocabularyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    language: str
    word: str
    translation: str
    context_sentence: str | None
    ease_factor: float
    interval_days: int
    repetition_count: int
    next_review_at: datetime
    created_at: datetime
    updated_at: datetime


class VocabularySimilarityMatch(VocabularyRead):
    """Enriched schema returned by vector similarity queries."""
    similarity_score: float = Field(..., ge=0.0, le=1.0)