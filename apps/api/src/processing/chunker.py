import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import tiktoken
from apps.api.src.core.config import settings
from apps.api.src.processing.extractors.base import ExtractedSection
from apps.api.src.processing.normalizer import TextNormalizer

logger = logging.getLogger("ai_knowledge_assistant.processing.chunker")


@dataclass
class ChunkResult:
    """Output representation of a generated chunk."""

    content: str
    chunk_index: int
    metadata: dict[str, Any]


class RecursiveTextChunker:
    """
    Deterministic, token-aware recursive text splitter.
    Splits text along semantic boundaries while preserving chunk overlap and section metadata.
    """

    DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", "; ", " ", ""]

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        tokenizer_model: str | None = None,
    ):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        self.tokenizer_model = tokenizer_model or settings.TOKENIZER_MODEL

        # Initialize tiktoken encoder with fallback
        try:
            self._tokenizer = tiktoken.get_encoding(self.tokenizer_model)
            self._count_tokens: Callable[[str], int] = lambda text: len(
                self._tokenizer.encode(text)
            )
        except Exception as e:
            logger.warning(
                f"Failed to load tiktoken encoding '{self.tokenizer_model}': {e}. Using character estimation fallback."
            )
            self._count_tokens = lambda text: max(1, len(text) // 4)

    def count_tokens(self, text: str) -> int:
        """Return token count for given text."""
        if not text:
            return 0
        return self._count_tokens(text)

    def _split_text_recursively(self, text: str, separators: list[str]) -> list[str]:
        """Recursively split text using hierarchy of separators until pieces fit within chunk_size."""
        final_chunks: list[str] = []
        separator = separators[-1]
        new_separators: list[str] = []

        # Find the first valid separator that appears in the text
        for i, s in enumerate(separators):
            if s == "":
                separator = s
                break
            if s in text:
                separator = s
                new_separators = separators[i + 1 :]
                break

        splits = text.split(separator) if separator else list(text)

        good_splits: list[str] = []
        for s in splits:
            if not s:
                continue
            if self.count_tokens(s) < self.chunk_size:
                good_splits.append(s)
            else:
                if good_splits:
                    merged = self._merge_splits(good_splits, separator)
                    final_chunks.extend(merged)
                    good_splits = []
                if not new_separators:
                    final_chunks.append(s)
                else:
                    other_chunks = self._split_text_recursively(s, new_separators)
                    final_chunks.extend(other_chunks)

        if good_splits:
            merged = self._merge_splits(good_splits, separator)
            final_chunks.extend(merged)

        return final_chunks

    def _merge_splits(self, splits: list[str], separator: str) -> list[str]:
        """Merge short splits into chunks up to chunk_size while maintaining chunk_overlap."""
        docs: list[str] = []
        current_doc: list[str] = []
        total_tokens = 0

        for s in splits:
            s_tokens = self.count_tokens(s)
            sep_tokens = self.count_tokens(separator) if current_doc and separator else 0

            if total_tokens + s_tokens + sep_tokens > self.chunk_size:
                if current_doc:
                    doc_str = separator.join(current_doc).strip()
                    if doc_str:
                        docs.append(doc_str)

                    # Pop elements from beginning until we satisfy chunk_overlap
                    while current_doc and (
                        total_tokens > self.chunk_overlap
                        or total_tokens + s_tokens + sep_tokens > self.chunk_size
                    ):
                        removed = current_doc.pop(0)
                        total_tokens -= self.count_tokens(removed)
                        if current_doc and separator:
                            total_tokens -= self.count_tokens(separator)
                        total_tokens = max(0, total_tokens)

                current_doc.append(s)
                total_tokens += s_tokens
            else:
                current_doc.append(s)
                total_tokens += s_tokens + sep_tokens

        if current_doc:
            doc_str = separator.join(current_doc).strip()
            if doc_str:
                docs.append(doc_str)

        return docs

    def chunk_sections(self, sections: list[ExtractedSection]) -> list[ChunkResult]:
        """
        Process extracted sections, normalize text, chunk deterministically,
        and attach structural and citation metadata.
        """
        chunks: list[ChunkResult] = []
        chunk_index = 0

        for section in sections:
            normalized_text = TextNormalizer.normalize(section.text)
            if not normalized_text:
                continue

            section_tokens = self.count_tokens(normalized_text)

            # If section already fits within chunk_size, keep it intact
            if section_tokens <= self.chunk_size:
                metadata = dict(section.metadata)
                metadata["token_count"] = section_tokens
                metadata["char_count"] = len(normalized_text)

                chunks.append(
                    ChunkResult(
                        content=normalized_text,
                        chunk_index=chunk_index,
                        metadata=metadata,
                    )
                )
                chunk_index += 1
            else:
                # Split large section recursively
                raw_pieces = self._split_text_recursively(normalized_text, self.DEFAULT_SEPARATORS)

                for piece in raw_pieces:
                    cleaned_piece = piece.strip()
                    if not cleaned_piece:
                        continue

                    piece_tokens = self.count_tokens(cleaned_piece)
                    metadata = dict(section.metadata)
                    metadata["token_count"] = piece_tokens
                    metadata["char_count"] = len(cleaned_piece)

                    chunks.append(
                        ChunkResult(
                            content=cleaned_piece,
                            chunk_index=chunk_index,
                            metadata=metadata,
                        )
                    )
                    chunk_index += 1

        logger.info(f"Chunked {len(sections)} sections into {len(chunks)} chunks.")
        return chunks
