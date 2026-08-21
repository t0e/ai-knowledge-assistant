import logging

import httpx
from apps.api.src.core.config import settings
from apps.api.src.core.exceptions import AppException, ValidationException
from apps.api.src.embeddings.base import BaseEmbeddingProvider

logger = logging.getLogger("ai_knowledge_assistant.embeddings.openai")


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """
    OpenAI Vector Embedding Provider using text-embedding-3-small or configured model.
    Communicates via asynchronous HTTP requests with batching and error translation.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        dimensions: int | None = None,
        batch_size: int | None = None,
    ):
        self._api_key = api_key or settings.OPENAI_API_KEY
        self._model_name = model_name or settings.EMBEDDING_MODEL
        self._dimensions = dimensions or settings.EMBEDDING_DIMENSIONS
        self._batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        self._api_url = "https://api.openai.com/v1/embeddings"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def model_name(self) -> str:
        return self._model_name

    def _validate_api_key(self) -> None:
        if not self._api_key or self._api_key.startswith("your_openai_api_key"):
            raise ValidationException(
                "OpenAI API key is not configured. Please set OPENAI_API_KEY in your environment or use mock provider for testing."
            )

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        self._validate_api_key()
        all_embeddings: list[list[float]] = []

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        # Process in batches to respect provider payload limits
        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(0, len(texts), self._batch_size):
                batch = texts[i : i + self._batch_size]
                # Replace newlines with spaces for optimal embedding per OpenAI guidelines
                cleaned_batch = [t.replace("\n", " ").strip() for t in batch]

                payload = {
                    "input": cleaned_batch,
                    "model": self._model_name,
                    "dimensions": self._dimensions,
                }

                try:
                    logger.info(
                        f"Sending batch of {len(batch)} chunks to OpenAI embedding API (model={self._model_name})."
                    )
                    response = await client.post(self._api_url, json=payload, headers=headers)
                except httpx.RequestError as e:
                    logger.error(f"OpenAI embedding network error: {e}")
                    raise AppException(
                        "Failed to connect to embedding provider. Please try again later.",
                        status_code=503,
                    ) from None

                if response.status_code == 401:
                    logger.error("OpenAI embedding authentication failed (invalid API key).")
                    raise AppException("Embedding service authentication failed.", status_code=500)
                elif response.status_code == 429:
                    logger.warning("OpenAI embedding rate limit exceeded.")
                    raise AppException(
                        "Embedding service rate limit exceeded. Please retry shortly.",
                        status_code=429,
                    )
                elif response.status_code != 200:
                    logger.error(f"OpenAI embedding error {response.status_code}: {response.text}")
                    raise AppException("Embedding generation failed.", status_code=502)

                data = response.json()
                sorted_items = sorted(data["data"], key=lambda x: x["index"])
                batch_embeddings = [item["embedding"] for item in sorted_items]

                for emb in batch_embeddings:
                    if len(emb) != self._dimensions:
                        raise AppException(
                            f"Embedding dimension mismatch: expected {self._dimensions}, got {len(emb)}",
                            status_code=500,
                        )

                all_embeddings.extend(batch_embeddings)

        return all_embeddings

    async def embed_query(self, query: str) -> list[float]:
        cleaned = query.replace("\n", " ").strip()
        if not cleaned:
            raise ValidationException("Query string cannot be empty.")
        embeddings = await self.embed_texts([cleaned])
        return embeddings[0]
