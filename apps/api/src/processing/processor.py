import logging

from apps.api.src.core.exceptions import ValidationException
from apps.api.src.processing.chunker import ChunkResult, RecursiveTextChunker
from apps.api.src.processing.extractors.base import BaseTextExtractor
from apps.api.src.processing.extractors.html import HtmlTextExtractor
from apps.api.src.processing.extractors.markdown import MarkdownTextExtractor
from apps.api.src.processing.extractors.pdf import PdfTextExtractor

logger = logging.getLogger("ai_knowledge_assistant.processing")


class DocumentProcessor:
    """Orchestrates document loading, text extraction, normalization, and chunking."""

    def __init__(
        self,
        chunker: RecursiveTextChunker | None = None,
    ):
        self.chunker = chunker or RecursiveTextChunker()
        self._extractors: dict[str, BaseTextExtractor] = {
            "pdf": PdfTextExtractor(),
            "markdown": MarkdownTextExtractor(),
            "website": HtmlTextExtractor(),
            "html": HtmlTextExtractor(),
            "htm": HtmlTextExtractor(),
        }

    def get_extractor(self, file_type: str) -> BaseTextExtractor:
        """Resolve appropriate extractor for given file type."""
        normalized_type = file_type.lower().strip()
        extractor = self._extractors.get(normalized_type)
        if not extractor:
            raise ValidationException(f"No text extractor configured for file type '{file_type}'.")
        return extractor

    def process(
        self,
        content: bytes,
        file_type: str,
        original_filename: str,
    ) -> list[ChunkResult]:
        """
        Execute full extraction, normalization, and chunking pipeline.
        Returns a list of deterministic ChunkResult objects.
        """
        if not content:
            raise ValidationException("Document content is empty.")

        logger.info(
            f"Starting processing pipeline for '{original_filename}' ({file_type}, {len(content)} bytes)."
        )
        extractor = self.get_extractor(file_type)

        # 1. Extraction (PDF / Markdown structural parsing)
        sections = extractor.extract(content, original_filename)
        if not sections:
            raise ValidationException(
                f"Failed to extract any text sections from '{original_filename}'."
            )

        # 2. Chunking & Normalization
        chunks = self.chunker.chunk_sections(sections)
        if not chunks:
            raise ValidationException(f"No valid text chunks generated from '{original_filename}'.")

        logger.info(
            f"Processing complete for '{original_filename}': generated {len(chunks)} chunks."
        )
        return chunks
