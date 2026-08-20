import logging
import uuid

from apps.api.src.api.dependencies import get_current_user, get_db
from apps.api.src.models.user import User
from apps.api.src.schemas.auth import MessageResponse
from apps.api.src.schemas.document import (
    DocumentChunkResponse,
    DocumentListResponse,
    DocumentResponse,
)
from apps.api.src.services.document_service import DocumentService
from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("ai_knowledge_assistant.api.documents")

router = APIRouter(prefix="/documents", tags=["Document Management"])


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and Process Knowledge Document",
    description="Uploads, stores, extracts text, and chunks a PDF or Markdown document into PostgreSQL.",
)
async def upload_document(
    file: UploadFile = File(
        ..., description="PDF (.pdf) or Markdown (.md, .markdown) file to upload"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    content = await file.read()
    original_filename = file.filename or "uploaded_file"
    document = await DocumentService.create_document(
        db=db,
        user_id=current_user.id,
        content=content,
        original_filename=original_filename,
    )
    return DocumentResponse.model_validate(document)


@router.get(
    "",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List User Documents",
    description="Retrieves a paginated list of documents uploaded by the authenticated user.",
)
async def list_documents(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    items, total, total_pages = await DocumentService.list_documents(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Document Metadata",
    description="Returns metadata for a specific document belonging to the authenticated user.",
)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    document = await DocumentService.get_document(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
    )
    return DocumentResponse.model_validate(document)


@router.get(
    "/{document_id}/chunks",
    response_model=list[DocumentChunkResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Document Chunks",
    description="Returns all extracted and normalized text chunks for a document belonging to the user.",
)
async def get_document_chunks(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentChunkResponse]:
    chunks = await DocumentService.get_document_chunks(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
    )
    return [
        DocumentChunkResponse(
            id=chunk.id,
            document_id=chunk.document_id,
            content=chunk.content,
            chunk_index=chunk.chunk_index,
            metadata=chunk.chunk_metadata,
            created_at=chunk.created_at,
        )
        for chunk in chunks
    ]


@router.delete(
    "/{document_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Document",
    description="Deletes a document record, its stored chunks, and the underlying stored file.",
)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await DocumentService.delete_document(
        db=db,
        user_id=current_user.id,
        document_id=document_id,
    )
    return MessageResponse(message="Document deleted successfully.")
