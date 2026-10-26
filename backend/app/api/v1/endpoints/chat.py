from collections.abc import Sequence
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser
from app.core.unit_of_work import UOWDep
from app.models.chat import ChatMessage, ChatSession
from app.schemas.chat import ChatMessageRead, ChatSessionCreate, ChatSessionRead
from app.services.ai_tutor_service import AITutorService

router = APIRouter(prefix="/sessions", tags=["chat"])

class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000, description="The user's message input")

@router.post(
    "",
    response_model=ChatSessionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat session"
)
async def create_chat_session(
    payload: ChatSessionCreate,
    uow: UOWDep,
    current_user: CurrentUser,
):
    """Generates a valid session UUID for the frontend."""
    new_session = ChatSession(
        user_id=current_user.id,
        target_language=payload.target_language,
        current_cefr_level=payload.current_cefr_level,
    )
    uow.chat.session.add(new_session)
    await uow.commit()
    return new_session

@router.get(
    "",
    response_model=list[ChatSessionRead],
    summary="List user chat sessions"
)
async def get_chat_sessions(
    uow: UOWDep,
    current_user: CurrentUser,
):
    """Populates the frontend sidebar history."""
    return await uow.chat.get_user_sessions(user_id=current_user.id)

@router.get(
    "/{session_id}/messages",
    response_model=list[ChatMessageRead],
    summary="Get messages for a chat session",
)
async def get_chat_messages(
    session_id: UUID,
    uow: UOWDep,
    current_user: CurrentUser,
) -> Sequence[ChatMessage]:
    session = await uow.chat.get(session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found.",
        )
    return await uow.chat.get_session_messages(session_id)

@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chat session",
)
async def delete_chat_session(
    session_id: UUID,
    uow: UOWDep,
    current_user: CurrentUser,
) -> None:
    deleted = await uow.chat.delete_user_session(session_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found.",
        )
    await uow.commit()

@router.post(
    "/{session_id}/messages",
    summary="Send user message and stream AI response via SSE",
    response_description="Server-Sent Events stream containing text deltas and metadata",
)
async def post_message_stream(
    request: Request,
    session_id: UUID,
    payload: SendMessageRequest,
    uow: UOWDep,
    current_user: CurrentUser,
) -> StreamingResponse:
    """
    Submits a message into an active chat session and returns an SSE stream.
    
    Yields:
        `data: {"event": "token", "delta": "..."}`
        `data: {"event": "done", "delta": ""}`
    """
    # Verify session ownership prior to establishing streaming connection
    session = await uow.chat.get(session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found.",
        )

    tutor_service = AITutorService(uow=uow, redis=request.app.state.redis_pool)

    return StreamingResponse(
        tutor_service.stream_chat_turn(
            session_id=session_id,
            user_id=current_user.id,
            user_message_content=payload.content,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disables proxy buffering on NGINX
        },
    )