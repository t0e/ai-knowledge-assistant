import logging
import uuid

from apps.api.src.core.exceptions import AppException, NotFoundException
from apps.api.src.embeddings.service import EmbeddingService, get_embedding_service
from apps.api.src.models.document import Document
from apps.api.src.models.document_chunk import DocumentChunk
from apps.api.src.processing.processor import DocumentProcessor
from apps.api.src.services.storage_service import BaseStorageService, get_storage_service
from apps.api.src.services.web_fetcher import WebFetcher, get_web_fetcher
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("ai_knowledge_assistant.services.processing")


class DocumentProcessingService:
    """Service orchestrating document text extraction, chunking, embedding generation, and vector persistence."""

    def __init__(
        self,
        processor: DocumentProcessor | None = None,
        storage_service: BaseStorageService | None = None,
        embedding_service: EmbeddingService | None = None,
        web_fetcher: WebFetcher | None = None,
    ):
        self.processor = processor or DocumentProcessor()
        self.storage = storage_service or get_storage_service()
        self.embeddings = embedding_service or get_embedding_service()
        self.web_fetcher = web_fetcher or get_web_fetcher()

    async def process_document(
        self,
        db: AsyncSession,
        document_id: uuid.UUID,
    ) -> Document:
        """
        Process an uploaded document or remote website URL:
        1. Fetch webpage or read file from storage
        2. Extract structured sections
        3. Normalize text
        4. Split into token-aware recursive chunks
        5. Generate vector embeddings in batch
        6. Persist chunks with pgvector embeddings to database
        7. Transition document status: uploaded -> processing -> ready (or failed)
        """
        stmt = select(Document).where(Document.id == document_id)
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()

        if not doc:
            raise NotFoundException("Document", str(document_id))

        # 1. Transition status to 'processing'
        doc.status = "processing"
        doc.error_message = None
        await db.commit()
        await db.refresh(doc)
        logger.info(f"Document id={doc.id} status changed to 'processing'.")

        try:
            # 2. Obtain raw content bytes (Remote Website Fetch or Local Storage Read)
            if doc.file_type == "website" or doc.source_url:
                target_url = doc.source_url or doc.original_filename
                logger.info(f"Fetching remote webpage for document id={doc.id}: {target_url}")
                page = await self.web_fetcher.fetch(target_url)
                file_bytes = page.content
                doc.file_size = len(file_bytes)

                # Cache HTML snapshot to storage
                relative_path = f"documents/{doc.user_id}/{doc.id}/page.html"
                try:
                    await self.storage.save_file(file_bytes, relative_path)
                    doc.storage_path = relative_path
                except Exception as e:
                    logger.warning(f"Could not cache HTML snapshot for doc {doc.id}: {e}")

                file_type = "website"
                filename = target_url
            else:
                file_bytes = await self.storage.read_file(doc.storage_path)
                file_type = doc.file_type
                filename = doc.original_filename

            # 3. Extract text, normalize, and chunk
            chunk_results = self.processor.process(
                content=file_bytes,
                file_type=file_type,
                original_filename=filename,
            )

            # Update document name with extracted title if website title is available
            first_meta = (
                chunk_results[0].metadata
                if chunk_results and isinstance(chunk_results[0].metadata, dict)
                else {}
            )
            if file_type == "website" and first_meta.get("title"):
                extracted_title = first_meta["title"]
                if extracted_title and extracted_title != "Webpage Content":
                    doc.name = str(extracted_title)[:255]

            # Inject source URL and title into chunk metadata for downstream citations
            if doc.source_url:
                for chunk in chunk_results:
                    if not isinstance(chunk.metadata, dict):
                        chunk.metadata = {}
                    chunk.metadata["url"] = doc.source_url
                    chunk.metadata["title"] = doc.name
                    chunk.metadata["source_type"] = "website"

            # 4. Generate batch vector embeddings
            logger.info(
                f"Generating vector embeddings for {len(chunk_results)} chunks (document id={doc.id})."
            )
            chunk_texts = [chunk.content for chunk in chunk_results]
            embeddings = await self.embeddings.embed_texts(chunk_texts)

            if len(embeddings) != len(chunk_results):
                raise AppException(
                    f"Embedding generation mismatch: expected {len(chunk_results)} vectors, got {len(embeddings)}",
                    status_code=500,
                )

            # 5. Clean up any existing chunks (idempotent reprocessing guarantee)
            await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))

            # 6. Bulk persist generated chunks with vector embeddings
            db_chunks = [
                DocumentChunk(
                    id=uuid.uuid4(),
                    document_id=doc.id,
                    content=chunk.content,
                    chunk_index=chunk.chunk_index,
                    chunk_metadata=chunk.metadata,
                    embedding=emb,
                )
                for chunk, emb in zip(chunk_results, embeddings, strict=True)
            ]
            db.add_all(db_chunks)

            # 7. Update document status to 'ready'
            doc.status = "ready"
            doc.error_message = None
            await db.commit()
            await db.refresh(doc)
            logger.info(
                f"Document id={doc.id} successfully processed with {len(db_chunks)} embedded chunks. Status changed to 'ready'."
            )
            return doc

        except Exception as e:
            logger.error(f"Processing/embedding failed for document id={doc.id}: {e}")
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
