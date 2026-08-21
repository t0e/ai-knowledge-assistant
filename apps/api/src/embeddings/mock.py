import hashlib
import logging
import math

from apps.api.src.embeddings.base import BaseEmbeddingProvider

logger = logging.getLogger("ai_knowledge_assistant.embeddings.mock")


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """
    Deterministic mock embedding provider for tests and local development.
    Produces unit-normalized float vectors with keyword-aware similarity without external API calls.
    """

    def __init__(self, dimensions: int = 1536, model_name: str = "mock-embedding-v1"):
        self._dimensions = dimensions
        self._model_name = model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def model_name(self) -> str:
        return self._model_name

    def _generate_vector(self, text: str) -> list[float]:
        """Generate deterministic unit-normalized float vector from text."""
        if not text:
            return [0.0] * self._dimensions

        # Base vector from full text hash
        text_hash = hashlib.sha256(text.encode("utf-8")).digest()
        vec = [0.0] * self._dimensions

        # Populate coordinates using hash chunks
        for i in range(self._dimensions):
            byte_val = text_hash[i % len(text_hash)]
            vec[i] = (byte_val / 128.0) - 1.0

        # Word-level keyword weighting so overlapping words increase cosine similarity
        words = text.lower().split()
        for word in words:
            word_hash = hashlib.sha256(word.encode("utf-8")).digest()
            for w_idx in range(min(64, self._dimensions)):
                target_idx = (
                    int.from_bytes(word_hash[w_idx % 4 : w_idx % 4 + 2], "big") + w_idx
                ) % self._dimensions
                vec[target_idx] += word_hash[w_idx % len(word_hash)] / 64.0

        # L2-normalize vector to unit length
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]

        return vec

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        logger.debug(f"MockEmbeddingProvider generating embeddings for {len(texts)} texts.")
        return [self._generate_vector(t) for t in texts]

    async def embed_query(self, query: str) -> list[float]:
        logger.debug(f"MockEmbeddingProvider generating embedding for query '{query[:30]}...'.")
        return self._generate_vector(query)
