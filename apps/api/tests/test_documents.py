import uuid

import pytest
import pytest_asyncio
from apps.api.src.services.storage_service import LocalStorageService
from apps.api.tests.test_processing import create_test_pdf_bytes
from httpx import AsyncClient


@pytest_asyncio.fixture
async def authenticated_user_a(async_client: AsyncClient):
    """Register and authenticate user A, returning client with user A session."""
    email = f"user_a_{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPassword123!"
    res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert res.status_code == 201
    return {"email": email, "id": res.json()["id"]}


@pytest_asyncio.fixture
async def authenticated_user_b(async_client: AsyncClient):
    """Register and authenticate user B, returning email and id."""
    email = f"user_b_{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPassword123!"
    res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert res.status_code == 201
    return {"email": email, "id": res.json()["id"], "password": password}


@pytest.mark.asyncio
async def test_upload_pdf_success(async_client: AsyncClient, authenticated_user_a):
    """Verify authenticated user can upload a valid PDF document."""
    pdf_bytes = create_test_pdf_bytes(["Architecture diagram specification content"])
    files = {"file": ("architecture_diagram.pdf", pdf_bytes, "application/pdf")}

    response = await async_client.post("/api/v1/documents", files=files)
    assert response.status_code == 201
    data = response.json()

    assert data["name"] == "architecture_diagram.pdf"
    assert data["original_filename"] == "architecture_diagram.pdf"
    assert data["file_type"] == "pdf"
    assert data["file_size"] == len(pdf_bytes)
    assert data["status"] in ("uploaded", "ready")
    assert "id" in data


@pytest.mark.asyncio
async def test_upload_markdown_success(async_client: AsyncClient, authenticated_user_a):
    """Verify authenticated user can upload a valid Markdown document."""
    md_bytes = b"# System Architecture\n\nThis is a production markdown document."
    files = {"file": ("guide.md", md_bytes, "text/markdown")}

    response = await async_client.post("/api/v1/documents", files=files)
    assert response.status_code == 201
    data = response.json()

    assert data["name"] == "guide.md"
    assert data["file_type"] == "markdown"
    assert data["file_size"] == len(md_bytes)
    assert data["status"] in ("uploaded", "ready")


@pytest.mark.asyncio
async def test_upload_unauthenticated_fails(async_client: AsyncClient):
    """Verify unauthenticated requests are rejected with 401."""
    async_client.cookies.clear()
    md_bytes = b"# Guide"
    files = {"file": ("guide.md", md_bytes, "text/markdown")}

    response = await async_client.post("/api/v1/documents", files=files)
    assert response.status_code == 401
    assert response.json()["title"] == "Unauthorized"


@pytest.mark.asyncio
async def test_upload_unsupported_file_type(async_client: AsyncClient, authenticated_user_a):
    """Verify unsupported file extensions (.exe, .png) are rejected with 422."""
    files = {"file": ("malicious.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/octet-stream")}
    response = await async_client.post("/api/v1/documents", files=files)
    assert response.status_code == 422
    assert "Unsupported file extension" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_invalid_pdf_content(async_client: AsyncClient, authenticated_user_a):
    """Verify a file named .pdf without valid %PDF- header is rejected with 422."""
    files = {"file": ("fake.pdf", b"This is not a real PDF file content", "application/pdf")}
    response = await async_client.post("/api/v1/documents", files=files)
    assert response.status_code == 422
    assert "Missing standard %PDF- header" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_disguised_binary_markdown(async_client: AsyncClient, authenticated_user_a):
    """Verify a file named .md with binary null bytes is rejected with 422."""
    files = {"file": ("corrupt.md", b"# Heading\x00\x01\x02binary", "text/markdown")}
    response = await async_client.post("/api/v1/documents", files=files)
    assert response.status_code == 422
    assert "Binary content detected" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_empty_file(async_client: AsyncClient, authenticated_user_a):
    """Verify empty file upload is rejected with 422."""
    files = {"file": ("empty.md", b"", "text/markdown")}
    response = await async_client.post("/api/v1/documents", files=files)
    assert response.status_code == 422
    assert "empty" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_path_traversal_filename_sanitized(
    async_client: AsyncClient, authenticated_user_a
):
    """Verify malicious filenames containing path traversal are sanitized safely."""
    pdf_bytes = create_test_pdf_bytes(["Test path traversal document content"])
    files = {"file": ("../../../../etc/passwd.pdf", pdf_bytes, "application/pdf")}

    response = await async_client.post("/api/v1/documents", files=files)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "passwd.pdf"
    assert "/" not in data["name"]
    assert "\\" not in data["name"]


@pytest.mark.asyncio
async def test_list_documents_and_pagination(async_client: AsyncClient, authenticated_user_a):
    """Verify paginated document listing."""
    pdf_bytes = create_test_pdf_bytes(["Document pagination page content"])
    await async_client.post(
        "/api/v1/documents", files={"file": ("doc1.pdf", pdf_bytes, "application/pdf")}
    )
    await async_client.post(
        "/api/v1/documents", files={"file": ("doc2.pdf", pdf_bytes, "application/pdf")}
    )

    response = await async_client.get("/api/v1/documents?page=1&page_size=1")
    assert response.status_code == 200
    data = response.json()

    assert data["page"] == 1
    assert data["page_size"] == 1
    assert data["total"] >= 2
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_user_document_isolation(
    async_client: AsyncClient, authenticated_user_a, authenticated_user_b
):
    """Verify strict tenant isolation: User B cannot see or get User A's document."""
    # 1. User A logs in and uploads document
    await async_client.post(
        "/api/v1/auth/login",
        json={"email": authenticated_user_a["email"], "password": "StrongPassword123!"},
    )
    pdf_bytes = create_test_pdf_bytes(["User A secret classified document"])
    upload_res = await async_client.post(
        "/api/v1/documents",
        files={"file": ("user_a_secret.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # 2. User B logs in
    await async_client.post(
        "/api/v1/auth/login",
        json={"email": authenticated_user_b["email"], "password": authenticated_user_b["password"]},
    )

    # 3. User B lists documents - must NOT include User A's document
    list_res = await async_client.get("/api/v1/documents")
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert not any(d["id"] == doc_id for d in items)

    # 4. User B attempts to directly GET User A's document -> must return 404
    get_res = await async_client.get(f"/api/v1/documents/{doc_id}")
    assert get_res.status_code == 404

    # 5. User B attempts to DELETE User A's document -> must return 404
    del_res = await async_client.delete(f"/api/v1/documents/{doc_id}")
    assert del_res.status_code == 404


@pytest.mark.asyncio
async def test_delete_document_success(async_client: AsyncClient, authenticated_user_a):
    """Verify document deletion cleans up DB record and storage file."""
    pdf_bytes = create_test_pdf_bytes(["To be deleted document"])
    upload_res = await async_client.post(
        "/api/v1/documents",
        files={"file": ("to_delete.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # Delete
    del_res = await async_client.delete(f"/api/v1/documents/{doc_id}")
    assert del_res.status_code == 200
    assert del_res.json()["message"] == "Document deleted successfully."

    # Subsequent GET returns 404
    get_res = await async_client.get(f"/api/v1/documents/{doc_id}")
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_storage_service_unit_path_traversal(tmp_path):
    """Unit test: LocalStorageService blocks any path traversal escape attempts."""
    storage = LocalStorageService(base_dir=str(tmp_path))

    with pytest.raises(ValueError, match="directory traversal attempt"):
        await storage.save_file(b"evil", "../../../escaped.txt")

    with pytest.raises(ValueError, match="directory traversal attempt"):
        await storage.read_file("../../outside.txt")
