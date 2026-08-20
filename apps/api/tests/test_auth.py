import uuid

import pytest
from apps.api.src.core.config import settings
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(async_client: AsyncClient):
    """Test successful user registration sets cookie and returns UserResponse without password hash."""
    unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": unique_email,
        "password": "StrongPassword123!",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()

    # UserResponse verification
    assert data["email"] == unique_email
    assert "id" in data
    assert data["is_active"] is True
    assert "created_at" in data
    assert "updated_at" in data

    # Security check: Password hash must NEVER be returned in response
    assert "password" not in data
    assert "password_hash" not in data

    # Cookie check: HttpOnly cookie must be present in response headers
    set_cookie_header = response.headers.get("set-cookie", "")
    assert settings.COOKIE_NAME in set_cookie_header
    assert "HttpOnly" in set_cookie_header


@pytest.mark.asyncio
async def test_register_duplicate_email(async_client: AsyncClient):
    """Test that registering an existing email returns 409 Conflict."""
    unique_email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": unique_email,
        "password": "StrongPassword123!",
    }
    # First registration
    res1 = await async_client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Second registration with same email
    res2 = await async_client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409
    data = res2.json()
    assert data["title"] == "Email Already Registered"


@pytest.mark.asyncio
async def test_register_invalid_email(async_client: AsyncClient):
    """Test that invalid email format is rejected with 422."""
    payload = {
        "email": "not-a-valid-email",
        "password": "StrongPassword123!",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password(async_client: AsyncClient):
    """Test that password shorter than 8 chars is rejected with 422."""
    payload = {
        "email": f"short_{uuid.uuid4().hex[:8]}@example.com",
        "password": "short",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient):
    """Test login with valid credentials sets cookie and returns UserResponse."""
    unique_email = f"login_{uuid.uuid4().hex[:8]}@example.com"
    password = "CorrectPassword123!"

    # Register first
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": password},
    )

    # Login
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": password},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == unique_email
    assert "password_hash" not in data

    set_cookie_header = response.headers.get("set-cookie", "")
    assert settings.COOKIE_NAME in set_cookie_header


@pytest.mark.asyncio
async def test_login_invalid_password(async_client: AsyncClient):
    """Test login with incorrect password returns 401 with generic error message."""
    unique_email = f"wrongpass_{uuid.uuid4().hex[:8]}@example.com"
    password = "CorrectPassword123!"

    await async_client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": password},
    )

    # Attempt with wrong password
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": "WrongPassword999!"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["title"] == "Authentication Failed"
    assert data["detail"] == "Invalid email or password."


@pytest.mark.asyncio
async def test_login_nonexistent_email(async_client: AsyncClient):
    """Test login with unknown email returns 401 with identical generic error message."""
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent_random_user_123@example.com", "password": "AnyPassword123!"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["title"] == "Authentication Failed"
    assert data["detail"] == "Invalid email or password."


@pytest.mark.asyncio
async def test_auth_me_authenticated(async_client: AsyncClient):
    """Test /api/v1/auth/me returns current user info when authenticated."""
    unique_email = f"me_{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPassword123!"

    # Register and capture cookie
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": password},
    )
    assert reg_res.status_code == 201

    # Call /auth/me with cookies maintained in the client session
    me_res = await async_client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    data = me_res.json()
    assert data["email"] == unique_email
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_auth_me_unauthenticated(async_client: AsyncClient):
    """Test /api/v1/auth/me returns 401 when no credentials are provided."""
    # Ensure fresh client without cookies
    async_client.cookies.clear()
    response = await async_client.get("/api/v1/auth/me")
    assert response.status_code == 401
    data = response.json()
    assert data["title"] == "Unauthorized"


@pytest.mark.asyncio
async def test_logout_clears_session(async_client: AsyncClient):
    """Test logout clears the auth cookie and prevents further authenticated calls."""
    unique_email = f"logout_{uuid.uuid4().hex[:8]}@example.com"
    password = "TestPassword123!"

    # Register/login
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": unique_email, "password": password},
    )

    # Verify authenticated
    me_res = await async_client.get("/api/v1/auth/me")
    assert me_res.status_code == 200

    # Logout
    logout_res = await async_client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200
    assert logout_res.json()["message"] == "Successfully logged out."

    # Subsequent /auth/me should fail with 401
    me_after_logout = await async_client.get("/api/v1/auth/me")
    assert me_after_logout.status_code == 401
