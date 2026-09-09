import json
from uuid import uuid4
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import CEFRLevel, ChatMessage, ChatSession, MessageRole
from app.models.user import User


@pytest.mark.anyio
async def test_post_message_stream_e2e(
    async_client: AsyncClient,
    db_session: AsyncSession,
    mock_user: User,
    mock_llm_stream: None,
) -> None:
    # 1. Arrange: Seed user and chat session into current transaction
    db_session.add(mock_user)
    await db_session.flush()

    session_id = uuid4()
    chat_session = ChatSession(
        id=session_id,
        user_id=mock_user.id,
        target_language="Spanish",
        current_cefr_level=CEFRLevel.A1,
        title="Practice Session",
    )
    db_session.add(chat_session)
    await db_session.flush()

    # 2. Act: Send message to streaming SSE endpoint
    payload = {"content": "Hola, quiero practicar español"}
    response = await async_client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json=payload,
    )

    # 3. Assert Response Headers
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert response.headers["cache-control"] == "no-cache"

    # 4. Parse SSE line-delimited events
    lines = [line.strip() for line in response.text.split("\n") if line.startswith("data: ")]
    assert len(lines) > 0

    tokens: list[str] = []
    received_done = False

    for line in lines:
        payload_data = json.loads(line.removeprefix("data: "))
        if payload_data["event"] == "token":
            tokens.append(payload_data["delta"])
        elif payload_data["event"] == "done":
            received_done = True

    assert received_done is True
    reconstructed_text = "".join(tokens)
    assert reconstructed_text == "¡Hola! ¿Cómo estás hoy?"

    # 5. Verify Database Persistence (both user and assistant messages stored)
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    result = await db_session.execute(stmt)
    messages = list(result.scalars().all())

    assert len(messages) == 2
    assert messages[0].role == MessageRole.USER
    assert messages[0].content == "Hola, quiero practicar español"

    assert messages[1].role == MessageRole.ASSISTANT
    assert messages[1].content == "¡Hola! ¿Cómo estás hoy?"


@pytest.mark.anyio
async def test_post_message_session_not_found(
    async_client: AsyncClient,
    mock_user: User,
) -> None:
    non_existent_session_id = uuid4()
    response = await async_client.post(
        f"/api/v1/sessions/{non_existent_session_id}/messages",
        json={"content": "Hello?"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Chat session not found."