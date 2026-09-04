from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.repositories.base import BaseRepository


class ChatRepository(BaseRepository[ChatSession]):
    """Repository handling ChatSession aggregates and ChatMessage history."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ChatSession, session)

    async def get_session_with_history(
        self,
        session_id: UUID,
        user_id: UUID,
        message_limit: int = 20,
    ) -> tuple[ChatSession | None, list[ChatMessage]]:
        """
        Loads a chat session with its most recent N messages returned in chronological order.
        
        Uses an isolated subquery/slice to avoid loading uncapped historical messages
        into memory while ensuring tenant boundary isolation via user_id.
        """
        # Fetch the root session entity
        stmt = select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        chat_session = result.scalar_one_or_none()

        if chat_session is None:
            return None, []

        # Retrieve the latest N messages (descending), then reverse for chronological context
        msg_stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(desc(ChatMessage.created_at))
            .limit(message_limit)
        )
        msg_result = await self.session.execute(msg_stmt)
        messages = list(msg_result.scalars().all())
        messages.reverse()

        return chat_session, messages

    async def append_message(
        self,
        session_id: UUID,
        role: MessageRole,
        content: str,
        token_count: int | None = None,
        audio_metadata: dict | None = None,
    ) -> ChatMessage:
        """Appends a new turn message to the session."""
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            token_count=token_count,
            audio_metadata=audio_metadata,
        )
        self.session.add(message)
        return message

    async def get_user_sessions(
        self,
        user_id: UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[ChatSession]:
        """Fetch recent sessions for a user."""
        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(desc(ChatSession.created_at))
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()