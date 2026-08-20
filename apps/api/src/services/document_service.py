import logging
import math
import uuid
from pathlib import Path

from apps.api.src.core.config import settings
from apps.api.src.core.exceptions import NotFoundException, ValidationException
from apps.api.src.models.document import Document
from apps.api.src.models.document_chunk import DocumentChunk
from apps.api.src.services.document_processing_service import (
    DocumentProcessingService,
    get_document_processing_service,
)
from apps.api.src.services.storage_service import BaseStorageService, get_storage_service
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("ai_knowledge_assistant.documents")


class DocumentService:
    """Service encapsulating document validation, storage, processing, and persistence operations."""

    @staticmethod
    def _validate_and_classify_file(content: bytes, original_filename: str) -> tuple[str, str]:
        """
        Validate file extension, size, and magic bytes/encoding.
        Returns (sanitized_name, normalized_file_type).
        """
        # 1. Size Validation
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(content) == 0:
            raise ValidationException("Uploaded file is empty.")
        if len(content) > max_bytes:
            raise ValidationException(
                f"File size exceeds the maximum limit of {settings.MAX_UPLOAD_SIZE_MB}MB."
            )

        # 2. Sanitize filename (extract pure basename, strip path traversal)
        safe_name = Path(original_filename).name.strip()
        if not safe_name or safe_name in (".", ".."):
            safe_name = "unnamed_document"

        ext = Path(safe_name).suffix.lower()
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise ValidationException(
                f"Unsupported file extension '{ext}'. Allowed types: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )

        # 3. Deep Content Verification
        if ext == ".pdf":
            # PDF magic header check: %PDF-
            if not content.startswith(b"%PDF-"):
                raise ValidationException("Invalid PDF file: Missing standard %PDF- header.")
            file_type = "pdf"
        elif ext in (".md", ".markdown"):
            # Markdown UTF-8 validation & binary character check
            try:
                decoded = content.decode("utf-8")
                if "\x00" in decoded:
                    raise ValidationException("Invalid Markdown file: Binary content detected.")
            except UnicodeDecodeError:
                raise ValidationException(
                    "Invalid Markdown file: Content must be valid UTF-8 text."
                ) from None
            file_type = "markdown"
        else:
            raise ValidationException("Unsupported file type.")

        return safe_name, file_type

    @staticmethod
    async def create_document(
        db: AsyncSession,
        user_id: uuid.UUID,
        content: bytes,
        original_filename: str,
        storage_service: BaseStorageService | None = None,
        processing_service: DocumentProcessingService | None = None,
    ) -> Document:
        """Validate, store, record, and process a new uploaded document."""
        storage = storage_service or get_storage_service()
        processor = processing_service or get_document_processing_service()

        safe_name, file_type = DocumentService._validate_and_classify_file(
            content, original_filename
        )

        doc_id = uuid.uuid4()
        extension = ".pdf" if file_type == "pdf" else ".md"
        relative_path = f"documents/{user_id}/{doc_id}/original{extension}"

        # 1. Save file to storage abstraction
        await storage.save_file(content, relative_path)

        # 2. Persist record to database
        try:
            document = Document(
                id=doc_id,
                user_id=user_id,
                name=safe_name,
                original_filename=original_filename,
                file_type=file_type,
                file_size=len(content),
                storage_path=relative_path,
                status="uploaded",
            )
            db.add(document)
            await db.commit()
            await db.refresh(document)
            logger.info(
                f"Successfully uploaded and persisted document id={doc_id} for user_id={user_id}"
            )
        except Exception as e:
            logger.error(
                f"Database error while creating document record, rolling back storage: {e}"
            )
            await storage.delete_file(relative_path)
            raise

        # 3. Synchronously process document into text chunks
        processed_document = await processor.process_document(db, document.id)
        return processed_document

    @staticmethod
    async def get_document(
        db: AsyncSession,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> Document:
        """Fetch document guaranteeing user ownership; returns 404 on any access violation."""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
        )
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()
        if not doc:
            raise NotFoundException("Document", str(document_id))
        return doc

    @staticmethod
    async def list_documents(
        db: AsyncSession,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Document], int, int]:
        """List user-scoped documents with pagination."""
        offset = (page - 1) * page_size

        # Count total
        count_stmt = select(func.count(Document.id)).where(Document.user_id == user_id)
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one() or 0

        # Query page items
        items_stmt = (
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items_result = await db.execute(items_stmt)
        items = list(items_result.scalars().all())

        total_pages = math.ceil(total / page_size) if total > 0 else 1
        return items, total, total_pages

    @staticmethod
    async def get_document_chunks(
        db: AsyncSession,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> list[DocumentChunk]:
        """Fetch all chunks for a document belonging to the authenticated user."""
        # Ensure document exists and belongs to user
        await DocumentService.get_document(db, user_id, document_id)

        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def delete_document(
        db: AsyncSession,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        storage_service: BaseStorageService | None = None,
    ) -> bool:
        """Delete document file, chunks (via cascade), and database row."""
        storage = storage_service or get_storage_service()
        doc = await DocumentService.get_document(db, user_id, document_id)

        # Delete physical file
        await storage.delete_file(doc.storage_path)

        # Delete DB row (cascades to document_chunks)
        await db.delete(doc)
        await db.commit()
        logger.info(f"Successfully deleted document id={document_id} for user_id={user_id}")
        return True
