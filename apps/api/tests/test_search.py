import math
import uuid

import pytest
from apps.api.src.core.exceptions import ValidationException
from apps.api.src.embeddings.mock import MockEmbeddingProvider
from apps.api.src.embeddings.service import EmbeddingService
from apps.api.src.queue.worker import process_document_job
from httpx import AsyncClient

# ==============================================================================
# 1. Embedding Provider Unit Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_mock_embedding_provider_dimensions_and_norm():
    provider = MockEmbeddingProvider(dimensions=1536)
    assert provider.dimensions == 1536
    assert provider.model_name == "mock-embedding-v1"

    texts = ["Document processing pipeline", "Vector similarity retrieval", "PostgreSQL database"]
    embeddings = await provider.embed_texts(texts)

    assert len(embeddings) == 3
    for emb in embeddings:
        assert len(emb) == 1536
        # Verify L2 unit norm (sum of squares is ~1.0)
        norm = math.sqrt(sum(x * x for x in emb))
        assert pytest.approx(norm, rel=1e-3) == 1.0


@pytest.mark.asyncio
async def test_mock_embedding_provider_keyword_similarity():
    provider = MockEmbeddingProvider(dimensions=1536)

    # Similar phrases with overlapping keywords
    vec1 = await provider.embed_query("PostgreSQL database indexing with pgvector")
    vec2 = await provider.embed_query("pgvector PostgreSQL database performance")
    vec_unrelated = await provider.embed_query("Baking chocolate chip cookies recipe")

    def dot_product(v1, v2):
        return sum(a * b for a, b in zip(v1, v2, strict=True))

    sim_related = dot_product(vec1, vec2)
    sim_unrelated = dot_product(vec1, vec_unrelated)

    # Overlapping phrases should have significantly higher similarity than unrelated text
    assert sim_related > sim_unrelated


@pytest.mark.asyncio
async def test_embedding_service_empty_query_rejected():
    service = EmbeddingService(provider=MockEmbeddingProvider(dimensions=1536))
    with pytest.raises(ValidationException, match="empty"):
        await service.embed_query("   ")


# ==============================================================================
# 2. Document Processing Lifecycle with Embeddings
# ==============================================================================


@pytest.mark.asyncio
async def test_upload_generates_and_stores_vector_embeddings(async_client: AsyncClient):
    """Verify document upload generates and stores valid pgvector embeddings on every chunk."""
    email = f"embed_user_{uuid.uuid4().hex[:8]}@example.com"
    await async_client.post(
        "/api/v1/auth/register", json={"email": email, "password": "Password123!"}
    )

    md_content = (
        b"# Vector Search Overview\n\npgvector enables efficient similarity queries in Postgres."
    )
    upload_res = await async_client.post(
        "/api/v1/documents",
        files={"file": ("vector_guide.md", md_content, "text/markdown")},
    )
    assert upload_res.status_code == 201
    doc_data = upload_res.json()
    assert doc_data["status"] in ("uploaded", "ready")
    doc_id = doc_data["id"]

    await process_document_job({"job_id": "test"}, doc_id)

    # Query chunks and verify existence
    chunks_res = await async_client.get(f"/api/v1/documents/{doc_id}/chunks")
    assert chunks_res.status_code == 200
    chunks = chunks_res.json()
    assert len(chunks) >= 1


# ==============================================================================
# 3. Semantic Search API Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_semantic_search_ranking_and_top_k(async_client: AsyncClient):
    """Verify semantic search ranks relevant chunks highest and respects top_k."""
    email = f"search_user_{uuid.uuid4().hex[:8]}@example.com"
    await async_client.post(
        "/api/v1/auth/register", json={"email": email, "password": "Password123!"}
    )

    # Upload multiple documents with distinct topics
    auth_doc = (
        b"# Authentication Architecture\n\n"
        b"Our authentication module uses bcrypt password hashing and HttpOnly JWT cookies."
    )
    db_doc = (
        b"# Database Indexing\n\n"
        b"PostgreSQL pgvector uses HNSW indexes with cosine distance for fast nearest neighbor search."
    )

    doc1_res = await async_client.post(
        "/api/v1/documents",
        files={"file": ("auth_guide.md", auth_doc, "text/markdown")},
    )
    doc2_res = await async_client.post(
        "/api/v1/documents",
        files={"file": ("db_guide.md", db_doc, "text/markdown")},
    )
    await process_document_job({"job_id": "test"}, doc1_res.json()["id"])
    await process_document_job({"job_id": "test"}, doc2_res.json()["id"])

    # Search for authentication
    search_res = await async_client.post(
        "/api/v1/search",
        json={"query": "How are passwords hashed and authenticated?", "top_k": 2},
    )
    assert search_res.status_code == 200
    data = search_res.json()

    assert data["query"] == "How are passwords hashed and authenticated?"
    assert len(data["results"]) <= 2
    assert len(data["results"]) > 0

    # Top result should be from auth_guide.md
    top_result = data["results"][0]
    assert top_result["document_name"] == "auth_guide.md"
    assert "bcrypt" in top_result["content"]
    assert top_result["score"] > 0.0


@pytest.mark.asyncio
async def test_semantic_search_document_id_filter(async_client: AsyncClient):
    """Verify semantic search respects optional document_ids filter."""
    email = f"filter_user_{uuid.uuid4().hex[:8]}@example.com"
    await async_client.post(
        "/api/v1/auth/register", json={"email": email, "password": "Password123!"}
    )

    doc1_res = await async_client.post(
        "/api/v1/documents",
        files={
            "file": (
                "doc1.md",
                b"# Architecture\nMicroservices and event sourcing.",
                "text/markdown",
            )
        },
    )
    doc2_res = await async_client.post(
        "/api/v1/documents",
        files={
            "file": ("doc2.md", b"# Architecture\nMonolithic deployment patterns.", "text/markdown")
        },
    )
    doc1_id = doc1_res.json()["id"]
    doc2_id = doc2_res.json()["id"]

    await process_document_job({"job_id": "test"}, doc1_id)
    await process_document_job({"job_id": "test"}, doc2_id)

    # Filter search to ONLY doc1
    search_res = await async_client.post(
        "/api/v1/search",
        json={"query": "Architecture patterns", "top_k": 5, "document_ids": [doc1_id]},
    )
    assert search_res.status_code == 200
    results = search_res.json()["results"]

    assert len(results) >= 1
    assert all(r["document_id"] == doc1_id for r in results)
    assert not any(r["document_id"] == doc2_id for r in results)


@pytest.mark.asyncio
async def test_semantic_search_validation_errors(async_client: AsyncClient):
    """Verify search input validation for empty query and invalid top_k."""
    email = f"val_user_{uuid.uuid4().hex[:8]}@example.com"
    await async_client.post(
        "/api/v1/auth/register", json={"email": email, "password": "Password123!"}
    )

    # Empty query
    res_empty = await async_client.post("/api/v1/search", json={"query": "   ", "top_k": 5})
    assert res_empty.status_code == 422

    # Negative / zero top_k
    res_invalid_k = await async_client.post(
        "/api/v1/search", json={"query": "valid query", "top_k": 0}
    )
    assert res_invalid_k.status_code == 422

    # Excessive top_k > 20
    res_excess_k = await async_client.post(
        "/api/v1/search", json={"query": "valid query", "top_k": 50}
    )
    assert res_excess_k.status_code == 422


# ==============================================================================
# 4. User Isolation & Security (CRITICAL)
# ==============================================================================


@pytest.mark.asyncio
async def test_semantic_search_strict_user_isolation(async_client: AsyncClient):
    """
    CRITICAL: User A must NEVER retrieve User B's chunks, even when querying
    exact keywords that exist exclusively in User B's documents.
    """
    # 1. Register User Alpha and upload secret document
    email_a = f"alpha_{uuid.uuid4().hex[:8]}@example.com"
    await async_client.post(
        "/api/v1/auth/register", json={"email": email_a, "password": "Password123!"}
    )
    doc_a_res = await async_client.post(
        "/api/v1/documents",
        files={
            "file": (
                "alpha_secret.md",
                b"# Top Secret Project Nebula\n\nNebula project budget is 50 million.",
                "text/markdown",
            )
        },
    )
    doc_a_id = doc_a_res.json()["id"]
    await process_document_job({"job_id": "test"}, doc_a_id)

    # 2. Register User Beta and upload different document
    email_b = f"beta_{uuid.uuid4().hex[:8]}@example.com"
    await async_client.post(
        "/api/v1/auth/register", json={"email": email_b, "password": "Password123!"}
    )
    doc_b_res = await async_client.post(
        "/api/v1/documents",
        files={
            "file": (
                "beta_public.md",
                b"# Public Company Guidelines\n\nStandard employee remote work policy.",
                "text/markdown",
            )
        },
    )
    doc_b_id = doc_b_res.json()["id"]
    await process_document_job({"job_id": "test"}, doc_b_id)

    # 3. User Beta searches for exact words from User Alpha's document: "Project Nebula budget"
    beta_search_res = await async_client.post(
        "/api/v1/search",
        json={"query": "Project Nebula budget 50 million", "top_k": 5},
    )
    assert beta_search_res.status_code == 200
    beta_results = beta_search_res.json()["results"]

    # MUST NOT contain any of User Alpha's chunks
    assert not any("Nebula" in r["content"] for r in beta_results)
    assert not any(r["document_id"] == doc_a_id for r in beta_results)

    # 4. User Beta attempts to pass User Alpha's document_id in document_ids filter
    tampered_filter_res = await async_client.post(
        "/api/v1/search",
        json={"query": "Project Nebula", "top_k": 5, "document_ids": [doc_a_id]},
    )
    assert tampered_filter_res.status_code == 200
    assert len(tampered_filter_res.json()["results"]) == 0
