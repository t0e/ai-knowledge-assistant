import logging
import uuid
from dataclasses import dataclass
from typing import Any

from apps.api.src.core.config import settings
from apps.api.src.core.exceptions import ValidationException
from apps.api.src.embeddings.service import EmbeddingService, get_embedding_service
from apps.api.src.models.document import Document
from apps.api.src.models.document_chunk import DocumentChunk
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("ai_knowledge_assistant.services.search")


@dataclass
class SearchResultItem:
    """Individual retrieved chunk result with similarity score and metadata."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    original_filename: str
    content: str
    score: float
    metadata: dict[str, Any]
    source_url: str | None = None


class SemanticSearchService:
    """Service executing vector similarity search against PostgreSQL pgvector."""

    def __init__(self, embedding_service: EmbeddingService | None = None):
        self.embeddings = embedding_service or get_embedding_service()

    async def search(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        query: str,
        top_k: int = 5,
        document_ids: list[uuid.UUID] | None = None,
    ) -> list[SearchResultItem]:
        """
        Execute vector similarity search scoped strictly to the authenticated user.
        Uses pgvector cosine distance (1 - distance = cosine similarity).
        """
        # 1. Validation
        cleaned_query = query.strip() if query else ""
        if not cleaned_query:
            raise ValidationException("Search query cannot be empty.")

        if top_k < 1 or top_k > settings.MAX_TOP_K:
            raise ValidationException(f"top_k must be between 1 and {settings.MAX_TOP_K}.")

        # 2. Query Embedding Generation
        query_vector = await self.embeddings.embed_query(cleaned_query)

        # 3. Vector Similarity Query with Enforced SQL-Level User Ownership
        # Cosine distance in pgvector: <=> operator
        # Cosine similarity score = 1.0 - cosine_distance
        cosine_distance_expr = DocumentChunk.embedding.cosine_distance(query_vector)
        similarity_score_expr = (1.0 - cosine_distance_expr).label("score")

        stmt = (
            select(
                DocumentChunk.id.label("chunk_id"),
                DocumentChunk.document_id,
                Document.name.label("document_name"),
                Document.original_filename,
                Document.source_url,
                DocumentChunk.content,
                similarity_score_expr,
                DocumentChunk.chunk_metadata,
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(Document.user_id == user_id)
            .where(Document.status == "ready")
            .where(DocumentChunk.embedding.isnot(None))
        )

        # Optional document_ids filter (automatically restricted to current user via the JOIN above)
        if document_ids:
            stmt = stmt.where(Document.id.in_(document_ids))

        # Order by ascending cosine distance (closest vectors first)
        stmt = stmt.order_by(cosine_distance_expr.asc()).limit(top_k)

        result = await db.execute(stmt)
        rows = result.all()

        results = [
            SearchResultItem(
                chunk_id=row.chunk_id,
                document_id=row.document_id,
                document_name=row.document_name,
                original_filename=row.original_filename,
                source_url=row.source_url,
                content=row.content,
                score=round(float(row.score), 4),
                metadata=dict(row.chunk_metadata),
            )
            for row in rows
        ]

        logger.info(
            f"Semantic search for user_id={user_id} (query='{cleaned_query[:30]}...', top_k={top_k}) returned {len(results)} chunks."
        )
        return results


_search_service_instance: SemanticSearchService | None = None


def get_search_service() -> SemanticSearchService:
    """Dependency / Singleton factory for SemanticSearchService."""
    global _search_service_instance
    if _search_service_instance is None:
        _search_service_instance = SemanticSearchService()
    return _search_service_instance
