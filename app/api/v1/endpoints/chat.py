from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.unit_of_work import UOWDep
from app.models.user import User
from app.services.ai_tutor_service import AITutorService

router = APIRouter(prefix="/sessions", tags=["chat"])


# Mock auth dependency for reference; replace with actual JWT dependency
async def get_current_user() -> User:
    # Simulates authenticated user context
    user = User(email="learner@example.com", is_active=True)
    user.id = UUID("11111111-1111-1111-1111-111111111111")
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000, description="The user's message input")


@router.post(
    "/{session_id}/messages",
    summary="Send user message and stream AI response via SSE",
    response_description="Server-Sent Events stream containing text deltas and metadata",
)
async def post_message_stream(
    session_id: UUID,
    payload: SendMessageRequest,
    uow: UOWDep,
    current_user: CurrentUserDep,
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

    tutor_service = AITutorService(uow=uow)

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