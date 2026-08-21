import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CitationResponse(BaseModel):
    """Citation metadata linking an answer claim to a source chunk."""

    model_config = ConfigDict(from_attributes=True)

    source_id: int = Field(..., description="Deterministic source number, e.g. 1 for [1]")
    document_id: uuid.UUID = Field(..., description="ID of source document")
    document_name: str = Field(..., description="Display name of source document")
    source_url: str | None = Field(None, description="Original webpage URL if source is a website")
    chunk_id: uuid.UUID = Field(..., description="ID of retrieved chunk")
    page: int | None = Field(None, description="Page number for PDF documents")
    heading: str | None = Field(None, description="Section heading for Markdown documents")
    content_preview: str = Field(..., description="Short snippet of retrieved text content")
    score: float = Field(..., description="Cosine similarity score")


class MessageResponse(BaseModel):
    """Chat message response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique message ID")
    conversation_id: uuid.UUID = Field(..., description="Conversation ID")
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message text content")
    citations: list[CitationResponse] = Field(
        default_factory=list, description="Associated source citations"
    )
    created_at: datetime = Field(..., description="Creation timestamp")


class SendMessageRequest(BaseModel):
    """Request payload for sending a chat message."""

    content: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="User question or prompt",
        examples=["What are the vacation policies in the employee handbook?"],
    )
    document_ids: list[uuid.UUID] | None = Field(
        None,
        description="Optional list of document IDs to scope retrieval to",
    )
    top_k: int | None = Field(
        5,
        ge=1,
        le=20,
        description="Number of chunks to retrieve for context",
    )


class ConversationCreateRequest(BaseModel):
    """Payload to create a new conversation."""

    title: str | None = Field(
        None,
        max_length=255,
        description="Optional title for the conversation",
        examples=["HR Policy Inquiry"],
    )


class ConversationResponse(BaseModel):
    """Conversation summary response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique conversation ID")
    user_id: uuid.UUID = Field(..., description="Owner user ID")
    title: str = Field(..., description="Conversation title")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    message_count: int = Field(0, description="Total number of messages")


class ConversationDetailResponse(BaseModel):
    """Detailed conversation response including all messages."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique conversation ID")
    user_id: uuid.UUID = Field(..., description="Owner user ID")
    title: str = Field(..., description="Conversation title")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    messages: list[MessageResponse] = Field(
        default_factory=list, description="Messages in chronological order"
    )


class ConversationListResponse(BaseModel):
    """List of user conversations."""

    items: list[ConversationResponse] = Field(..., description="List of conversations")
    total: int = Field(..., description="Total count")
