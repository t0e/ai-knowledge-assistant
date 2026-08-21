import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_conversations(async_client: AsyncClient):
    """Verify creating and listing user conversations."""
    email = f"conv_user_{uuid.uuid4().hex[:8]}@example.com"
    await async_client.post(
        "/api/v1/auth/register", json={"email": email, "password": "Password123!"}
    )

    # Create 2 conversations
    c1 = await async_client.post("/api/v1/conversations", json={"title": "First Conversation"})
    assert c1.status_code == 201
    c1_data = c1.json()
    assert c1_data["title"] == "First Conversation"

    c2 = await async_client.post("/api/v1/conversations", json={"title": "Second Conversation"})
    assert c2.status_code == 201

    # List conversations
    list_res = await async_client.get("/api/v1/conversations")
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["title"] == "Second Conversation"  # Ordered by updated_at desc


@pytest.mark.asyncio
async def test_get_and_delete_conversation(async_client: AsyncClient):
    """Verify getting conversation detail and deleting conversation."""
    email = f"conv_del_{uuid.uuid4().hex[:8]}@example.com"
    await async_client.post(
        "/api/v1/auth/register", json={"email": email, "password": "Password123!"}
    )

    create_res = await async_client.post("/api/v1/conversations", json={"title": "To Delete"})
    conv_id = create_res.json()["id"]

    # Get conversation
    get_res = await async_client.get(f"/api/v1/conversations/{conv_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "To Delete"
    assert len(get_res.json()["messages"]) == 0

    # Delete conversation
    del_res = await async_client.delete(f"/api/v1/conversations/{conv_id}")
    assert del_res.status_code == 200

    # Getting deleted conversation returns 404
    get_after = await async_client.get(f"/api/v1/conversations/{conv_id}")
    assert get_after.status_code == 404


@pytest.mark.asyncio
async def test_conversation_multi_tenant_isolation(async_client: AsyncClient):
    """CRITICAL: User A must never access or modify User B's conversation."""
    # User A
    email_a = f"user_a_{uuid.uuid4().hex[:8]}@example.com"
    await async_client.post(
        "/api/v1/auth/register", json={"email": email_a, "password": "Password123!"}
    )
    c_a = await async_client.post("/api/v1/conversations", json={"title": "User A Private Chat"})
    conv_a_id = c_a.json()["id"]

    # User B
    email_b = f"user_b_{uuid.uuid4().hex[:8]}@example.com"
    await async_client.post(
        "/api/v1/auth/register", json={"email": email_b, "password": "Password123!"}
    )

    # User B attempts to GET User A's conversation
    get_b = await async_client.get(f"/api/v1/conversations/{conv_a_id}")
    assert get_b.status_code == 404

    # User B attempts to DELETE User A's conversation
    del_b = await async_client.delete(f"/api/v1/conversations/{conv_a_id}")
    assert del_b.status_code == 404
