import logging
import re

from apps.api.src.core.exceptions import ValidationException
from apps.api.src.processing.extractors.base import BaseTextExtractor, ExtractedSection
from bs4 import BeautifulSoup, Comment, Tag

logger = logging.getLogger("ai_knowledge_assistant.processing.html")

# Elements to discard completely
DISCARD_TAGS = {
    "script",
    "style",
    "noscript",
    "nav",
    "footer",
    "header",
    "aside",
    "form",
    "button",
    "svg",
    "canvas",
    "dialog",
    "iframe",
    "input",
    "textarea",
    "select",
    "option",
}

# Common CSS class / ID markers for noisy non-content elements
NOISE_CLASSES_AND_IDS = re.compile(
    r"(cookie|banner|advertisement|ads|popup|modal|menu|navbar|sidebar|footer|social-share|newsletter)",
    re.IGNORECASE,
)


class HtmlTextExtractor(BaseTextExtractor):
    """
    Extracts structured, noise-free text sections from HTML web pages.
    Removes navigation, scripts, footers, and cookie banners while preserving
    titles, headings, code blocks, lists, and paragraphs.
    """

    def extract(self, file_bytes: bytes, filename: str) -> list[ExtractedSection]:
        if not file_bytes:
            raise ValidationException("HTML content is empty.")

        try:
            # Attempt lxml parser, fall back to standard html.parser
            try:
                soup = BeautifulSoup(file_bytes, "lxml")
            except Exception:
                soup = BeautifulSoup(file_bytes, "html.parser")
        except Exception as e:
            raise ValidationException(f"Failed to parse HTML document: {e}") from None

        # 1. Extract Page Title
        page_title = "Webpage Content"
        title_tag = soup.find("title")
        og_title = soup.find("meta", property="og:title")
        if title_tag and title_tag.string:
            page_title = title_tag.string.strip()
        elif og_title and og_title.get("content"):
            page_title = og_title["content"].strip()
        elif soup.find("h1"):
            page_title = soup.find("h1").get_text().strip()

        # Clean title string
        page_title = re.sub(r"\s+", " ", page_title)

        # 2. Remove HTML comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # 3. Remove unwanted tags
        for tag_name in DISCARD_TAGS:
            for element in soup.find_all(tag_name):
                element.decompose()

        # 4. Remove common noisy divs / sections (cookie banners, sidebars, ads)
        for element in soup.find_all(True):
            if not isinstance(element, Tag):
                continue
            element_classes = " ".join(element.get("class", []))
            element_id = element.get("id", "")
            if NOISE_CLASSES_AND_IDS.search(element_classes) or NOISE_CLASSES_AND_IDS.search(
                element_id
            ):
                # Don't delete if it's the main container itself
                if element.name not in ("main", "article", "body", "html"):
                    element.decompose()

        # 5. Locate Core Content Root (prefer <main>, <article>, or fallback to <body>)
        content_root = soup.find("main") or soup.find("article") or soup.find("body") or soup

        # 6. Extract structured sections grouped by headings (h1 - h6)
        sections: list[ExtractedSection] = []
        current_heading = page_title or "Overview"
        heading_stack = [page_title or "Overview"]
        current_blocks: list[str] = []

        def flush_current_section():
            if current_blocks:
                section_text = "\n\n".join(current_blocks).strip()
                if section_text:
                    sections.append(
                        ExtractedSection(
                            text=section_text,
                            metadata={
                                "heading": current_heading,
                                "section_path": " > ".join(heading_stack),
                                "source_type": "website",
                                "title": page_title,
                                "original_filename": filename,
                            },
                        )
                    )
                current_blocks.clear()

        # Walk through block elements in document order
        heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}
        for element in content_root.find_all(
            ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "blockquote", "table"]
        ):
            if not isinstance(element, Tag):
                continue

            tag_name = element.name.lower()

            if tag_name in heading_tags:
                heading_text = element.get_text(separator=" ", strip=True)
                if not heading_text:
                    continue

                flush_current_section()

                level = int(tag_name[1])  # 1 to 6
                if level <= len(heading_stack):
                    heading_stack = heading_stack[:level]
                    heading_stack.append(heading_text)
                else:
                    heading_stack.append(heading_text)

                current_heading = heading_text
                current_blocks.append(f"## {heading_text}")

            elif tag_name == "pre":
                code_text = element.get_text(strip=True)
                if code_text:
                    current_blocks.append(f"```\n{code_text}\n```")

            elif tag_name == "table":
                # Extract text rows from table
                rows = []
                for tr in element.find_all("tr"):
                    cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
                    if any(cells):
                        rows.append(" | ".join(cells))
                if rows:
                    current_blocks.append("\n".join(rows))

            else:  # p, li, blockquote
                block_text = element.get_text(separator=" ", strip=True)
                # Filter out very short UI remnants (e.g. single symbols, 'click here', empty strings)
                if block_text and len(block_text) > 3:
                    current_blocks.append(block_text)

        flush_current_section()

        # If heading-based extraction returned empty (e.g. page without standard block structure), extract text paragraphs
        if not sections:
            raw_body_text = content_root.get_text(separator="\n", strip=True)
            cleaned_text = re.sub(r"\n\s*\n+", "\n\n", raw_body_text).strip()
            if cleaned_text:
                sections.append(
                    ExtractedSection(
                        text=cleaned_text,
                        metadata={
                            "heading": page_title,
                            "section_path": page_title,
                            "source_type": "website",
                            "title": page_title,
                            "original_filename": filename,
                        },
                    )
                )

        if not sections:
            raise ValidationException(
                "No readable textual content could be extracted from the webpage."
            )

        logger.info(
            f"Extracted {len(sections)} structural sections from HTML '{filename}' (Title: '{page_title}')."
        )
        return sections
