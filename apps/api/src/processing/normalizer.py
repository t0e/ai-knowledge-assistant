import re
import unicodedata


class TextNormalizer:
    """Utility class for cleaning and normalizing document text prior to chunking."""

    # Matches 3 or more consecutive newlines
    EXCESSIVE_NEWLINES = re.compile(r"\n{3,}")
    # Matches multiple horizontal whitespace chars (spaces/tabs), but not newlines
    EXCESSIVE_SPACES = re.compile(r"[^\S\r\n]{2,}")
    # Matches non-printable control characters (excluding newline \n, tab \t, carriage return \r)
    CONTROL_CHARS = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]")

    @classmethod
    def normalize(cls, text: str) -> str:
        """
        Normalize raw text by cleaning formatting artifacts while preserving meaningful content.
        """
        if not text:
            return ""

        # 1. Unicode Normalization (NFC standard)
        normalized = unicodedata.normalize("NFC", text)

        # 2. Standardize carriage returns
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

        # 3. Strip non-printable control characters
        normalized = cls.CONTROL_CHARS.sub("", normalized)

        # 4. Normalize trailing whitespace on each line
        lines = [cls.EXCESSIVE_SPACES.sub(" ", line).strip() for line in normalized.splitlines()]
        rejoined = "\n".join(lines)

        # 5. Collapse excessive blank lines (more than 2 consecutive newlines into 2)
        rejoined = cls.EXCESSIVE_NEWLINES.sub("\n\n", rejoined)

        return rejoined.strip()
