from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseUUIDModel

if TYPE_CHECKING:
    from app.models.user import User


class CEFRLevel(StrEnum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatSession(BaseUUIDModel):
    __tablename__ = "chat_sessions"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    target_language: Mapped[str] = mapped_column(String(50), nullable=False)
    current_cefr_level: Mapped[CEFRLevel] = mapped_column(
        SQLEnum(
            CEFRLevel,
            native_enum=False,
            values_callable=lambda obj: [e.value for e in obj],
            length=10,
        ),
        default=CEFRLevel.A1,
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at.asc()",
    )


class ChatMessage(BaseUUIDModel):
    __tablename__ = "chat_messages"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[MessageRole] = mapped_column(
        SQLEnum(
            MessageRole,
            native_enum=False,
            values_callable=lambda obj: [e.value for e in obj],
            length=20,
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    audio_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
    )
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class VocabularyMemory(BaseUUIDModel):
    __tablename__ = "vocabulary_memories"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    word: Mapped[str] = mapped_column(String(100), nullable=False)
    translation: Mapped[str] = mapped_column(String(255), nullable=False)
    context_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Spaced Repetition (SuperMemo-2)
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5, nullable=False)
    interval_days: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    repetition_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_review_at: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # pgvector 1536-dimensional embeddings
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="vocabulary_items")

    __table_args__ = (
        CheckConstraint("ease_factor >= 1.3", name="check_min_ease_factor"),
        Index(
            "idx_vocab_vector_cosine",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("idx_vocab_user_word", "user_id", "word", unique=True),
    )