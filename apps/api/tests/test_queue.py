import uuid
from unittest.mock import AsyncMock

import pytest
from apps.api.src.core.database import AsyncSessionLocal
from apps.api.src.models.document import Document
from apps.api.src.models.document_chunk import DocumentChunk
from apps.api.src.queue.service import QueueService
from apps.api.src.queue.worker import process_document_job
from apps.api.src.services.document_service import DocumentService
from apps.api.tests.test_processing import create_test_pdf_bytes
from httpx import AsyncClient
from sqlalchemy import select


@pytest.mark.asyncio
async def test_upload_returns_uploaded_status_immediately(async_client: AsyncClient):
    """
    Verify upload API returns HTTP 201 immediately with status 'uploaded'
    without waiting synchronously for chunking and embedding.
    """
    email = f"async_user_{uuid.uuid4().hex[:8]}@example.com"
    await async_client.post(
        "/api/v1/auth/register", json={"email": email, "password": "Password123!"}
    )

    pdf_bytes = create_test_pdf_bytes(["Page 1: Architecture overview."])
    response = await async_client.post(
        "/api/v1/documents",
        files={"file": ("async_test.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201
    doc_data = response.json()
    assert doc_data["status"] == "uploaded"
    doc_id = uuid.UUID(doc_data["id"])

    # At the moment of upload response, chunks are not yet processed
    async with AsyncSessionLocal() as db:
        chunks = (
            (await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc_id)))
            .scalars()
            .all()
        )
        assert len(chunks) == 0


@pytest.mark.asyncio
async def test_worker_processes_job_to_ready():
    """Verify background worker job processes uploaded document to ready with embeddings."""
    mock_queue = AsyncMock(spec=QueueService)
    mock_queue.enqueue_document_processing = AsyncMock(return_value=True)

    async with AsyncSessionLocal() as db:
        from apps.api.src.core.security import hash_password
        from apps.api.src.models.user import User

        user = User(
            id=uuid.uuid4(),
            email=f"worker_user_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("Pass123!"),
        )
        db.add(user)
        await db.commit()

        pdf_bytes = create_test_pdf_bytes(
            ["Page 1: Distributed caching.", "Page 2: Sharding and replication."]
        )
        doc = await DocumentService.create_document(
            db, user.id, pdf_bytes, "caching_spec.pdf", queue_service=mock_queue, sync_process=False
        )
        assert doc.status == "uploaded"

    # Execute worker job
    ctx = {"job_id": "test-job-1", "job_try": 1}
    job_result = await process_document_job(ctx, str(doc.id))
    assert job_result["status"] == "ready"

    # Verify final state in DB
    async with AsyncSessionLocal() as db2:
        updated_doc = await db2.get(Document, doc.id)
        assert updated_doc.status == "ready"
        chunks = (
            (await db2.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc.id)))
            .scalars()
            .all()
        )
        assert len(chunks) >= 2
        for chunk in chunks:
            assert chunk.embedding is not None


@pytest.mark.asyncio
async def test_worker_idempotent_duplicate_execution():
    """Verify executing the worker job multiple times on the same document does not duplicate chunks."""
    mock_queue = AsyncMock(spec=QueueService)
    mock_queue.enqueue_document_processing = AsyncMock(return_value=True)

    async with AsyncSessionLocal() as db:
        from apps.api.src.core.security import hash_password
        from apps.api.src.models.user import User

        user = User(
            id=uuid.uuid4(),
            email=f"idempotent_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("Pass123!"),
        )
        db.add(user)
        await db.commit()

        doc_md = b"# Policy\n\nSection 1: Security guidelines."
        doc = await DocumentService.create_document(
            db, user.id, doc_md, "security.md", queue_service=mock_queue, sync_process=False
        )

    ctx = {"job_id": "test-job-dup", "job_try": 1}
    # Run 1
    res1 = await process_document_job(ctx, str(doc.id))
    assert res1["status"] == "ready"

    async with AsyncSessionLocal() as db:
        chunks_1 = (
            (await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc.id)))
            .scalars()
            .all()
        )
        count_1 = len(chunks_1)
        assert count_1 >= 1

    # Run 2 (Duplicate execution)
    res2 = await process_document_job(ctx, str(doc.id))
    assert res2["status"] == "ready"

    async with AsyncSessionLocal() as db:
        chunks_2 = (
            (await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc.id)))
            .scalars()
            .all()
        )
        assert len(chunks_2) == count_1  # Exact same count, no duplicates!


@pytest.mark.asyncio
async def test_worker_deleted_document_while_queued():
    """Verify worker cleanly skips processing if document was deleted prior to worker execution."""
    fake_doc_id = uuid.uuid4()
    ctx = {"job_id": "test-job-deleted", "job_try": 1}
    result = await process_document_job(ctx, str(fake_doc_id))
    assert result["status"] == "skipped"
    assert result["reason"] == "document_deleted"
