import logging
import sys
import uuid

from apps.api.src.core.config import settings
from apps.api.src.core.database import AsyncSessionLocal
from apps.api.src.core.exceptions import NotFoundException, ValidationException
from apps.api.src.models.document import Document
from apps.api.src.services.document_processing_service import get_document_processing_service
from arq import Retry, run_worker
from arq.connections import RedisSettings
from sqlalchemy import select

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ai_knowledge_assistant.worker")


async def process_document_job(ctx: dict, document_id: str) -> dict:
    """
    Background worker job to extract, chunk, embed, and persist document knowledge.
    Safe against duplicate execution (Idempotent) and handles deleted documents cleanly.
    """
    job_id = ctx.get("job_id", "unknown")
    job_try = ctx.get("job_try", 1)
    logger.info(
        f"Starting processing job (job_id={job_id}, document_id={document_id}, try={job_try}/{settings.JOB_MAX_RETRIES})"
    )

    doc_uuid = uuid.UUID(document_id)

    async with AsyncSessionLocal() as db:
        # 1. Check if document exists (Delete while queued handling)
        stmt = select(Document).where(Document.id == doc_uuid)
        result = await db.execute(stmt)
        doc = result.scalar_one_or_none()

        if not doc:
            logger.info(
                f"Document {document_id} was deleted before worker pickup. Clean exit without processing."
            )
            return {"status": "skipped", "reason": "document_deleted"}

        # 2. Invoke DocumentProcessingService pipeline
        processor = get_document_processing_service()
        try:
            processed_doc = await processor.process_document(db, doc_uuid)
            logger.info(
                f"Successfully processed document (job_id={job_id}, document_id={document_id}, status={processed_doc.status})"
            )
            return {"status": "ready", "document_id": document_id}

        except ValidationException as val_err:
            # Permanent error (corrupt format, empty file, etc.) - do not retry
            logger.warning(
                f"Permanent validation error processing document {document_id}: {val_err}. Marking failed without retry."
            )
            return {"status": "failed", "reason": str(val_err)}

        except NotFoundException:
            # Document deleted during active processing
            logger.info(f"Document {document_id} was removed during processing pipeline execution.")
            return {"status": "skipped", "reason": "document_deleted_during_processing"}

        except Exception as exc:
            # Transient error (network timeout, temporary provider outage) - retry up to max_tries
            logger.error(f"Transient error during document processing (try {job_try}): {exc}")
            if job_try < settings.JOB_MAX_RETRIES:
                logger.info(
                    f"Scheduling retry for document {document_id} in {settings.JOB_RETRY_DELAY}s (try {job_try + 1})..."
                )
                raise Retry(defer=settings.JOB_RETRY_DELAY) from exc

            logger.critical(
                f"Exhausted all {settings.JOB_MAX_RETRIES} retries for document {document_id}. Final status: failed."
            )
            return {"status": "failed", "reason": "Retries exhausted"}


async def on_startup(ctx: dict) -> None:
    logger.info("=" * 70)
    logger.info(f"Starting Document Processing Worker on queue '{settings.PROCESSING_QUEUE}'")
    logger.info(f"Redis URL: {settings.REDIS_URL}")
    logger.info(f"Job Timeout: {settings.JOB_TIMEOUT}s | Max Retries: {settings.JOB_MAX_RETRIES}")
    logger.info("=" * 70)


async def on_shutdown(ctx: dict) -> None:
    logger.info("Shutting down Document Processing Worker gracefully...")


class WorkerSettings:
    """ARQ Worker Configuration."""

    functions = [process_document_job]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    queue_name = settings.PROCESSING_QUEUE
    max_jobs = 10
    job_timeout = settings.JOB_TIMEOUT
    max_tries = settings.JOB_MAX_RETRIES
    on_startup = on_startup
    on_shutdown = on_shutdown


if __name__ == "__main__":
    run_worker(WorkerSettings)
