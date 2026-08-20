import io
import logging

import pypdf
from apps.api.src.core.exceptions import ValidationException
from apps.api.src.processing.extractors.base import BaseTextExtractor, ExtractedSection
from pypdf.errors import PdfReadError

logger = logging.getLogger("ai_knowledge_assistant.processing.pdf")


class PdfTextExtractor(BaseTextExtractor):
    """Extracts text content page-by-page from PDF documents using pypdf."""

    def extract(self, file_bytes: bytes, filename: str) -> list[ExtractedSection]:
        if not file_bytes:
            raise ValidationException("PDF file is empty.")

        try:
            stream = io.BytesIO(file_bytes)
            reader = pypdf.PdfReader(stream)
        except (PdfReadError, Exception) as e:
            logger.error(f"Failed to read PDF file '{filename}': {e}")
            raise ValidationException(f"Invalid or corrupted PDF file: {e}") from None

        if reader.is_encrypted:
            try:
                # Try empty password default decrypt
                reader.decrypt("")
            except Exception:
                raise ValidationException(
                    "Encrypted or password-protected PDF files are not supported."
                ) from None

        total_pages = len(reader.pages)
        if total_pages == 0:
            raise ValidationException("PDF file contains no pages.")

        sections: list[ExtractedSection] = []
        total_extracted_chars = 0

        for page_idx, page in enumerate(reader.pages):
            page_number = page_idx + 1
            try:
                page_text = page.extract_text() or ""
            except Exception as e:
                logger.warning(
                    f"Error extracting text from page {page_number} in '{filename}': {e}"
                )
                page_text = ""

            cleaned_page = page_text.strip()
            total_extracted_chars += len(cleaned_page)

            if cleaned_page:
                sections.append(
                    ExtractedSection(
                        text=cleaned_page,
                        metadata={
                            "page": page_number,
                            "total_pages": total_pages,
                            "source_type": "pdf",
                            "original_filename": filename,
                        },
                    )
                )

        if total_extracted_chars == 0:
            logger.warning(
                f"PDF '{filename}' produced 0 extractable characters (likely scanned/image-only)."
            )
            raise ValidationException(
                "PDF contains no extractable text. Scanned or image-only documents are not currently supported."
            )

        logger.info(
            f"Extracted {len(sections)} page sections from PDF '{filename}' ({total_pages} total pages)."
        )
        return sections
