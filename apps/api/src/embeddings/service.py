import logging

from apps.api.src.core.config import settings
from apps.api.src.core.exceptions import ValidationException
from apps.api.src.embeddings.base import BaseEmbeddingProvider
from apps.api.src.embeddings.mock import MockEmbeddingProvider
from apps.api.src.embeddings.openai import OpenAIEmbeddingProvider

logger = logging.getLogger("ai_knowledge_assistant.embeddings")


class EmbeddingService:
    """High-level embedding orchestrator supporting pluggable providers."""

    def __init__(self, provider: BaseEmbeddingProvider | None = None):
        is_placeholder_key = not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith(
            "your_openai_api_key"
        )
        if provider:
            self._provider = provider
        elif settings.EMBEDDING_PROVIDER.lower() == "mock" or (
            is_placeholder_key and settings.ENVIRONMENT == "development"
        ):
            logger.info(
                "Using MockEmbeddingProvider for deterministic offline embedding generation."
            )
            self._provider = MockEmbeddingProvider(dimensions=settings.EMBEDDING_DIMENSIONS)
        else:
            logger.info(
                f"Using OpenAIEmbeddingProvider (model={settings.EMBEDDING_MODEL}, dims={settings.EMBEDDING_DIMENSIONS})."
            )
            self._provider = OpenAIEmbeddingProvider()

    @property
    def provider(self) -> BaseEmbeddingProvider:
        return self._provider

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for a list of texts."""
        if not texts:
            return []
        return await self._provider.embed_texts(texts)

    async def embed_query(self, query: str) -> list[float]:
        """Generate vector embedding for a single search query."""
        if not query or not query.strip():
            raise ValidationException("Search query cannot be empty.")
        return await self._provider.embed_query(query.strip())


_embedding_service_instance: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Dependency / Singleton provider for EmbeddingService."""
    global _embedding_service_instance
    if _embedding_service_instance is None:
        _embedding_service_instance = EmbeddingService()
    return _embedding_service_instance
