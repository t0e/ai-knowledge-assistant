from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractedSection:
    """Represents a discrete structural section extracted from a document."""

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseTextExtractor(ABC):
    """Abstract base class for document text extractors."""

    @abstractmethod
    def extract(self, file_bytes: bytes, filename: str) -> list[ExtractedSection]:
        """Extract structured text sections from raw document bytes."""
        pass
