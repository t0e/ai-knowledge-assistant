import logging
import uuid

from apps.api.src.api.dependencies import get_current_user, get_db
from apps.api.src.models.user import User
from apps.api.src.schemas.auth import MessageResponse as AuthMessageResponse
from apps.api.src.schemas.conversation import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
    MessageResponse,
    SendMessageRequest,
)
from apps.api.src.services.conversation_service import ConversationService
from apps.api.src.services.rag_service import RAGService, get_rag_service
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("ai_knowledge_assistant.api.conversations")

router = APIRouter(prefix="/conversations", tags=["Conversations & Chat"])


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Conversation",
    description="Creates a new conversation container for the authenticated user.",
)
async def create_conversation(
    payload: ConversationCreateRequest = ConversationCreateRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    conv = await ConversationService.create_conversation(
        db=db,
        user_id=current_user.id,
        title=payload.title,
    )
    return ConversationResponse(
        id=conv.id,
        user_id=conv.user_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=0,
    )


@router.get(
    "",
    response_model=ConversationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List User Conversations",
    description="Retrieves a paginated list of conversations owned by the authenticated user.",
)
async def list_conversations(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationListResponse:
    items_with_counts, total = await ConversationService.list_conversations(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    return ConversationListResponse(
        items=[
            ConversationResponse(
                id=conv.id,
                user_id=conv.user_id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=count,
            )
            for conv, count in items_with_counts
        ],
        total=total,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Conversation Detail",
    description="Retrieves a conversation and all its messages in chronological order.",
)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetailResponse:
    conv = await ConversationService.get_conversation(
        db=db,
        user_id=current_user.id,
        conversation_id=conversation_id,
    )
    return ConversationDetailResponse(
        id=conv.id,
        user_id=conv.user_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[
            MessageResponse(
                id=m.id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                citations=m.citations,
                created_at=m.created_at,
            )
            for m in conv.messages
        ],
    )


@router.delete(
    "/{conversation_id}",
    response_model=AuthMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Conversation",
    description="Deletes a conversation and all its messages.",
)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuthMessageResponse:
    await ConversationService.delete_conversation(
        db=db,
        user_id=current_user.id,
        conversation_id=conversation_id,
    )
    return AuthMessageResponse(message="Conversation deleted successfully.")


@router.post(
    "/{conversation_id}/messages",
    summary="Send Message with Streaming RAG Response",
    description="Sends a user question, retrieves relevant document chunks, and streams the grounded answer via Server-Sent Events (SSE).",
)
async def send_message_stream(
    conversation_id: uuid.UUID,
    payload: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    rag_service: RAGService = Depends(get_rag_service),
) -> StreamingResponse:
    generator = rag_service.stream_chat(
        db=db,
        user_id=current_user.id,
        conversation_id=conversation_id,
        query=payload.content,
        document_ids=payload.document_ids,
        top_k=payload.top_k or 5,
    )
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
