from abc import ABC, abstractmethod


class BaseEmbeddingProvider(ABC):
    """Abstract base class for vector embedding providers."""

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Generate vector embeddings for a batch of text strings.
        Must return a list of float vectors of length equal to self.dimensions.
        """
        pass

    @abstractmethod
    async def embed_query(self, query: str) -> list[float]:
        """
        Generate a single vector embedding for a query string.
        Must return a float vector of length equal to self.dimensions.
        """
        pass

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the vector dimensionality of this embedding provider."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        pass
