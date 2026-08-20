import logging
import re

from apps.api.src.core.exceptions import ValidationException
from apps.api.src.processing.extractors.base import BaseTextExtractor, ExtractedSection

logger = logging.getLogger("ai_knowledge_assistant.processing.markdown")


class MarkdownTextExtractor(BaseTextExtractor):
    """Extracts structured text sections from Markdown documents preserving heading context."""

    HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def extract(self, file_bytes: bytes, filename: str) -> list[ExtractedSection]:
        if not file_bytes:
            raise ValidationException("Markdown file is empty.")

        try:
            raw_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raise ValidationException("Markdown file contains invalid UTF-8 encoding.") from None

        if "\x00" in raw_text:
            raise ValidationException("Markdown file contains invalid binary content.")

        stripped = raw_text.strip()
        if not stripped:
            raise ValidationException("Markdown file contains no readable content.")

        lines = raw_text.splitlines()
        sections: list[ExtractedSection] = []

        current_heading = "Document Root"
        heading_stack: list[str] = ["Document Root"]
        current_lines: list[str] = []
        in_code_block = False

        for line in lines:
            # Check for code fence toggling
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                current_lines.append(line)
                continue

            # Heading matching (only when outside fenced code blocks)
            match = self.HEADING_PATTERN.match(line)
            if match and not in_code_block:
                # Flush previous section
                if current_lines:
                    section_text = "\n".join(current_lines).strip()
                    if section_text:
                        sections.append(
                            ExtractedSection(
                                text=section_text,
                                metadata={
                                    "heading": current_heading,
                                    "section_path": " > ".join(heading_stack),
                                    "source_type": "markdown",
                                    "original_filename": filename,
                                },
                            )
                        )
                    current_lines = []

                level = len(match.group(1))
                heading_text = match.group(2).strip()

                # Adjust heading stack according to level
                # Ensure stack has enough depth or truncate
                if level <= len(heading_stack):
                    heading_stack = heading_stack[:level]
                    heading_stack.append(heading_text)
                else:
                    heading_stack.append(heading_text)

                current_heading = heading_text
                current_lines.append(line)
            else:
                current_lines.append(line)

        # Flush final section
        if current_lines:
            section_text = "\n".join(current_lines).strip()
            if section_text:
                sections.append(
                    ExtractedSection(
                        text=section_text,
                        metadata={
                            "heading": current_heading,
                            "section_path": " > ".join(heading_stack),
                            "source_type": "markdown",
                            "original_filename": filename,
                        },
                    )
                )

        if not sections:
            raise ValidationException("Markdown file contains no readable content.")

        logger.info(f"Extracted {len(sections)} structural sections from Markdown '{filename}'.")
        return sections
