import logging
import uuid

from apps.api.src.core.exceptions import AppException, NotFoundException
from apps.api.src.models.document import Document
from apps.api.src.models.document_chunk import DocumentChunk
from apps.api.src.processing.processor import DocumentProcessor
from apps.api.src.services.storage_service import BaseStorageService, get_storage_service
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("ai_knowledge_assistant.services.processing")


class DocumentProcessingService:
    """Service orchestrating document text extraction, chunking, and database persistence."""

    def __init__(
        self,
        processor: DocumentProcessor | None = None,
        storage_service: BaseStorageService | None = None,
    ):
        self.processor = processor or DocumentProcessor()
        self.storage = storage_service or get_storage_service()

    async def process_document(
        self,
        db: AsyncSession,
        document_id: uuid.UUID,
    ) -> Document:
        """
        Process an uploaded document: extract text, chunk content, and persist chunks to database.
        Transitions document status: uploaded -> processing -> ready (or failed).
        """
        stmt = select(Document).where(Document.id == document_id)
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()

        if not doc:
            raise NotFoundException("Document", str(document_id))

        # 1. Update status to 'processing'
        doc.status = "processing"
        doc.error_message = None
        await db.commit()
        await db.refresh(doc)
        logger.info(f"Document id={doc.id} status changed to 'processing'.")

        try:
            # 2. Read file from storage
            file_bytes = await self.storage.read_file(doc.storage_path)

            # 3. Extract text, normalize, and chunk
            chunk_results = self.processor.process(
                content=file_bytes,
                file_type=doc.file_type,
                original_filename=doc.original_filename,
            )

            # 4. Clean up any existing chunks (for idempotency / re-processing)
            await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))

            # 5. Bulk persist generated chunks
            db_chunks = [
                DocumentChunk(
                    id=uuid.uuid4(),
                    document_id=doc.id,
                    content=chunk.content,
                    chunk_index=chunk.chunk_index,
                    chunk_metadata=chunk.metadata,
                )
                for chunk in chunk_results
            ]
            db.add_all(db_chunks)

            # 6. Update document status to 'ready'
            doc.status = "ready"
            doc.error_message = None
            await db.commit()
            await db.refresh(doc)
            logger.info(
                f"Document id={doc.id} processed successfully into {len(db_chunks)} chunks. Status changed to 'ready'."
            )
            return doc

        except Exception as e:
            logger.error(f"Processing failed for document id={doc.id}: {e}")
            await db.rollback()

            # Mark document as failed with sanitized error summary
            err_msg = str(e)
            if isinstance(e, AppException):
                err_msg = e.detail
            elif len(err_msg) > 500:
                err_msg = err_msg[:500]

            doc.status = "failed"
            doc.error_message = err_msg
            await db.commit()
            await db.refresh(doc)
            return doc


_processing_service_instance: DocumentProcessingService | None = None


def get_document_processing_service() -> DocumentProcessingService:
    """Dependency / singleton factory for DocumentProcessingService."""
    global _processing_service_instance
    if _processing_service_instance is None:
        _processing_service_instance = DocumentProcessingService()
    return _processing_service_instance
