import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentChunkResponse(BaseModel):
    """Metadata response representing a single chunk of a document."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    content: str
    chunk_index: int
    chunk_metadata: dict[str, Any] = Field(..., alias="metadata")
    created_at: datetime


class DocumentResponse(BaseModel):
    """Metadata response representing an uploaded document."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID = Field(..., examples=["123e4567-e89b-12d3-a456-426614174000"])
    name: str = Field(..., examples=["Architecture Overview.pdf"])
    original_filename: str = Field(..., examples=["architecture.pdf"])
    file_type: str = Field(..., examples=["pdf"])
    file_size: int = Field(..., examples=[1048576])
    status: str = Field(..., examples=["ready"])
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """Paginated list of user documents."""

    items: list[DocumentResponse]
    total: int = Field(..., examples=[42])
    page: int = Field(..., examples=[1])
    page_size: int = Field(..., examples=[20])
    total_pages: int = Field(..., examples=[3])
