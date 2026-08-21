import uuid

import pytest
from apps.api.src.core.exceptions import ValidationException
from apps.api.src.processing.chunker import RecursiveTextChunker
from apps.api.src.processing.extractors.base import ExtractedSection
from apps.api.src.processing.extractors.markdown import MarkdownTextExtractor
from apps.api.src.processing.extractors.pdf import PdfTextExtractor
from apps.api.src.processing.normalizer import TextNormalizer
from apps.api.src.queue.worker import process_document_job
from httpx import AsyncClient


def create_test_pdf_bytes(pages_text: list[str]) -> bytes:
    """Helper to dynamically generate a valid standard PDF with given page texts."""
    body = bytearray()
    body.extend(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}

    def add_obj(num: int, data: bytes):
        offsets[num] = len(body)
        body.extend(f"{num} 0 obj\n".encode("ascii"))
        body.extend(data)
        body.extend(b"\nendobj\n")

    kids = " ".join([f"{4 + 2 * i} 0 R" for i in range(len(pages_text))])
    add_obj(1, b"<< /Type /Catalog /Pages 2 0 R >>")
    add_obj(2, f"<< /Type /Pages /Kids [{kids}] /Count {len(pages_text)} >>".encode("ascii"))
    add_obj(3, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for i, text in enumerate(pages_text):
        page_id = 4 + 2 * i
        content_id = 5 + 2 * i
        add_obj(
            page_id,
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
            ).encode("ascii"),
        )

        escaped = text.replace("(", "\\(").replace(")", "\\)")
        stream_bytes = f"BT /F1 12 Tf 100 700 Td ({escaped}) Tj ET".encode("ascii")
        content_data = (
            f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii")
            + stream_bytes
            + b"\nendstream"
        )
        add_obj(content_id, content_data)

    xref_offset = len(body)
    body.extend(b"xref\n")
    total_objs = 4 + 2 * len(pages_text)
    body.extend(f"0 {total_objs}\n".encode("ascii"))
    body.extend(b"0000000000 65535 f \n")
    for num in range(1, total_objs):
        offset = offsets[num]
        body.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    body.extend(b"trailer\n")
    body.extend(f"<< /Size {total_objs} /Root 1 0 R >>\n".encode("ascii"))
    body.extend(b"startxref\n")
    body.extend(f"{xref_offset}\n".encode("ascii"))
    body.extend(b"%%EOF\n")
    return bytes(body)


# ==============================================================================
# 1. Text Normalizer Tests
# ==============================================================================


def test_normalizer_excessive_whitespace_and_newlines():
    raw = "Line 1   with   spaces\n\n\n\n\nLine 2\r\n\r\nLine 3"
    cleaned = TextNormalizer.normalize(raw)
    assert cleaned == "Line 1 with spaces\n\nLine 2\n\nLine 3"


def test_normalizer_control_characters():
    raw = "Valid text\x00\x07with\x1fcontrol\x7fchars"
    cleaned = TextNormalizer.normalize(raw)
    assert cleaned == "Valid textwithcontrolchars"


def test_normalizer_unicode_preservation():
    raw = "Artificial Intelligence • 🤖 • Übergröße"
    cleaned = TextNormalizer.normalize(raw)
    assert cleaned == "Artificial Intelligence • 🤖 • Übergröße"


# ==============================================================================
# 2. Markdown Extractor Tests
# ==============================================================================


def test_markdown_extractor_headings_and_structure():
    md = (
        b"# System Architecture\n\n"
        b"This is the top-level overview.\n\n"
        b"## Authentication Module\n\n"
        b"We use HttpOnly cookies with JWT.\n\n"
        b"```python\n"
        b"# Code block with hashtag should not be heading\n"
        b"def login(): pass\n"
        b"```\n\n"
        b"## Storage Module\n\n"
        b"- Item 1\n- Item 2\n"
    )

    extractor = MarkdownTextExtractor()
    sections = extractor.extract(md, "test.md")

    assert len(sections) == 3
    assert sections[0].metadata["heading"] == "System Architecture"
    assert "System Architecture" in sections[0].text

    assert sections[1].metadata["heading"] == "Authentication Module"
    assert "def login(): pass" in sections[1].text

    assert sections[2].metadata["heading"] == "Storage Module"
    assert "Item 1" in sections[2].text


def test_markdown_extractor_empty_fails():
    extractor = MarkdownTextExtractor()
    with pytest.raises(ValidationException, match="empty"):
        extractor.extract(b"", "empty.md")


# ==============================================================================
# 3. PDF Extractor Tests
# ==============================================================================


def test_pdf_extractor_single_and_multi_page():
    pdf_bytes = create_test_pdf_bytes(
        ["Page One Content", "Page Two Analysis", "Page Three Conclusion"]
    )
    extractor = PdfTextExtractor()
    sections = extractor.extract(pdf_bytes, "report.pdf")

    assert len(sections) == 3
    assert sections[0].metadata["page"] == 1
    assert sections[0].metadata["total_pages"] == 3
    assert "Page One Content" in sections[0].text

    assert sections[1].metadata["page"] == 2
    assert "Page Two Analysis" in sections[1].text

    assert sections[2].metadata["page"] == 3
    assert "Page Three Conclusion" in sections[2].text


def test_pdf_extractor_corrupt_fails():
    extractor = PdfTextExtractor()
    with pytest.raises(ValidationException):
        extractor.extract(b"Not a real PDF", "bad.pdf")


# ==============================================================================
# 4. Recursive Chunker Tests
# ==============================================================================


def test_chunker_deterministic_and_ordering():
    chunker = RecursiveTextChunker(chunk_size=50, chunk_overlap=10)
    section = ExtractedSection(
        text="Sentence 1 about RAG. Sentence 2 about pgvector. Sentence 3 about PostgreSQL. Sentence 4 about FastAPI.",
        metadata={"page": 1, "source_type": "pdf"},
    )

    chunks = chunker.chunk_sections([section])
    assert len(chunks) >= 1
    for i, c in enumerate(chunks):
        assert c.chunk_index == i
        assert c.metadata["page"] == 1
        assert c.metadata["source_type"] == "pdf"
        assert len(c.content) > 0


def test_chunker_long_document_overlap():
    chunker = RecursiveTextChunker(chunk_size=15, chunk_overlap=5)
    long_text = (
        "Paragraph 1 contains substantial knowledge about RAG pipelines.\n\n"
        "Paragraph 2 provides detailed specifications on vector indexing.\n\n"
        "Paragraph 3 discusses hybrid semantic search and BM25.\n\n"
        "Paragraph 4 describes reranking with cross-encoders."
    )
    section = ExtractedSection(text=long_text, metadata={"heading": "Overview"})

    chunks = chunker.chunk_sections([section])
    assert len(chunks) >= 2
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1


@pytest.mark.asyncio
async def test_upload_pdf_processes_and_persists_chunks(async_client: AsyncClient):
    """Verify upload automatically processes PDF into document_chunks and transitions to ready."""
    email = f"proc_user_{uuid.uuid4().hex[:8]}@example.com"
    await async_client.post(
        "/api/v1/auth/register", json={"email": email, "password": "Password123!"}
    )

    pdf_bytes = create_test_pdf_bytes(
        ["Introduction to AI RAG System", "Vector Database Architecture"]
    )
    upload_res = await async_client.post(
        "/api/v1/documents",
        files={"file": ("rag_paper.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code == 201
    doc_data = upload_res.json()
    doc_id = doc_data["id"]
    assert doc_data["status"] in ("uploaded", "ready")
    assert doc_data["name"] == "rag_paper.pdf"

    # Execute worker processing
    await process_document_job({"job_id": "test"}, doc_id)

    # Query chunks endpoint
    chunks_res = await async_client.get(f"/api/v1/documents/{doc_id}/chunks")
    assert chunks_res.status_code == 200
    chunks = chunks_res.json()

    assert len(chunks) >= 2
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["metadata"]["page"] == 1
    assert "Introduction to AI RAG System" in chunks[0]["content"]

    assert chunks[1]["chunk_index"] == 1
    assert chunks[1]["metadata"]["page"] == 2
    assert "Vector Database Architecture" in chunks[1]["content"]

    # Test cascade delete: deleting document deletes chunks
    del_res = await async_client.delete(f"/api/v1/documents/{doc_id}")
    assert del_res.status_code == 200

    # Chunks endpoint now returns 404
    after_del_chunks = await async_client.get(f"/api/v1/documents/{doc_id}/chunks")
    assert after_del_chunks.status_code == 404


@pytest.mark.asyncio
async def test_upload_markdown_processes_and_persists_chunks(async_client: AsyncClient):
    """Verify upload automatically processes Markdown into document_chunks with heading metadata."""
    email = f"md_user_{uuid.uuid4().hex[:8]}@example.com"
    await async_client.post(
        "/api/v1/auth/register", json={"email": email, "password": "Password123!"}
    )

    md_content = (
        b"# FastAPI Guide\n\nFastAPI is modern and async.\n\n"
        b"## Dependency Injection\n\nUse Depends for modular auth and database sessions."
    )

    upload_res = await async_client.post(
        "/api/v1/documents",
        files={"file": ("fastapi_guide.md", md_content, "text/markdown")},
    )
    assert upload_res.status_code == 201
    doc_data = upload_res.json()
    doc_id = doc_data["id"]
    assert doc_data["status"] in ("uploaded", "ready")

    # Execute worker processing
    await process_document_job({"job_id": "test"}, doc_id)

    # Query chunks endpoint
    chunks_res = await async_client.get(f"/api/v1/documents/{doc_id}/chunks")
    assert chunks_res.status_code == 200
    chunks = chunks_res.json()

    assert len(chunks) >= 2
    assert chunks[0]["metadata"]["heading"] == "FastAPI Guide"
    assert chunks[1]["metadata"]["heading"] == "Dependency Injection"
