import logging

from apps.api.src.api.dependencies import get_current_user, get_db
from apps.api.src.models.user import User
from apps.api.src.schemas.search import SearchRequest, SearchResponse, SearchResultChunkResponse
from apps.api.src.services.search_service import SemanticSearchService, get_search_service
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("ai_knowledge_assistant.api.search")

router = APIRouter(prefix="/search", tags=["Semantic Search"])


@router.post(
    "",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic Vector Search",
    description="Embeds a search query and retrieves the most relevant document chunks for the authenticated user using pgvector.",
)
async def semantic_search(
    payload: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    search_service: SemanticSearchService = Depends(get_search_service),
) -> SearchResponse:
    results = await search_service.search(
        db=db,
        user_id=current_user.id,
        query=payload.query,
        top_k=payload.top_k,
        document_ids=payload.document_ids,
    )

    return SearchResponse(
        query=payload.query,
        total_results=len(results),
        results=[
            SearchResultChunkResponse(
                chunk_id=item.chunk_id,
                document_id=item.document_id,
                document_name=item.document_name,
                original_filename=item.original_filename,
                source_url=item.source_url,
                content=item.content,
                score=item.score,
                metadata=item.metadata,
            )
            for item in results
        ],
    )
