import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SearchRequest(BaseModel):
    """Payload for executing a semantic similarity search query."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language search query",
        examples=["How does password authentication work?"],
    )
    top_k: int = Field(
        5,
        ge=1,
        le=20,
        description="Maximum number of relevant chunks to retrieve",
        examples=[5],
    )
    document_ids: list[uuid.UUID] | None = Field(
        None,
        description="Optional list of document IDs to scope search within",
        examples=[["123e4567-e89b-12d3-a456-426614174000"]],
    )


class SearchResultChunkResponse(BaseModel):
    """Metadata and content for a retrieved matching chunk."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    original_filename: str
    source_url: str | None = None
    content: str
    score: float = Field(..., description="Cosine similarity score (0.0 to 1.0)")
    metadata: dict[str, Any] = Field(..., description="Section, heading, and page metadata")


class SearchResponse(BaseModel):
    """Ranked list of relevant knowledge chunks returned by semantic search."""

    query: str
    total_results: int
    results: list[SearchResultChunkResponse]
