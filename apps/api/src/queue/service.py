import logging
import uuid

from apps.api.src.core.config import settings
from arq.connections import ArqRedis, RedisSettings, create_pool

logger = logging.getLogger("ai_knowledge_assistant.queue")


class QueueService:
    """Service for enqueueing background jobs to Redis via ARQ."""

    def __init__(self, redis_pool: ArqRedis | None = None):
        self._redis_pool = redis_pool

    async def get_pool(self) -> ArqRedis:
        try:
            if self._redis_pool is not None:
                await self._redis_pool.ping()
                return self._redis_pool
        except Exception:
            self._redis_pool = None

        redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
        self._redis_pool = await create_pool(redis_settings)
        return self._redis_pool

    async def close(self) -> None:
        if self._redis_pool is not None:
            await self._redis_pool.close()
            self._redis_pool = None

    async def enqueue_document_processing(self, document_id: uuid.UUID) -> bool:
        """
        Enqueue document processing job asynchronously.
        Returns True if enqueued successfully, False if Redis is unreachable.
        """
        try:
            pool = await self.get_pool()
            job = await pool.enqueue_job(
                "process_document_job",
                str(document_id),
                _queue_name=settings.PROCESSING_QUEUE,
            )
            if job:
                logger.info(
                    f"Enqueued document processing job (job_id={job.job_id}, document_id={document_id})"
                )
                return True
            else:
                logger.warning(
                    f"Job not created (duplicate or queue full) for document_id={document_id}"
                )
                return False
        except Exception as e:
            logger.error(
                f"Failed to enqueue document processing job for document_id={document_id}: {e}"
            )
            return False


_queue_service_instance: QueueService | None = None


def get_queue_service() -> QueueService:
    global _queue_service_instance
    if _queue_service_instance is None:
        _queue_service_instance = QueueService()
    return _queue_service_instance
