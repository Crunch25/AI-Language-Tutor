from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.chat import CEFRLevel, MessageRole


# --- Chat Message Schemas ---
class ChatMessageBase(BaseModel):
    role: MessageRole
    content: str = Field(..., min_length=1)
    audio_metadata: dict[str, Any] | None = None


class ChatMessageCreate(ChatMessageBase):
    token_count: int | None = Field(default=None, ge=0)


class ChatMessageRead(ChatMessageBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    token_count: int | None
    created_at: datetime
    updated_at: datetime


# --- Chat Session Schemas ---
class ChatSessionCreate(BaseModel):
    target_language: str = Field(..., min_length=2, max_length=50, examples=["Spanish"])
    current_cefr_level: CEFRLevel = Field(default=CEFRLevel.A1)
    title: str | None = Field(default=None, max_length=120)


class ChatSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    target_language: str
    current_cefr_level: CEFRLevel
    title: str | None
    created_at: datetime
    updated_at: datetime


# --- Streaming SSE Chunk Schema ---
class AIStreamChunk(BaseModel):
    """Payload format streamed over Server-Sent Events (SSE)."""
    event: Literal["token", "grammar_correction", "vocab_hint", "done"] = "token"
    delta: str = ""
    metadata: dict[str, Any] | None = None