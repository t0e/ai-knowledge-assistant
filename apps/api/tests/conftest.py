from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from apps.api.src.core.config import settings
from apps.api.src.core.database import get_db
from apps.api.src.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


@pytest_asyncio.fixture(autouse=True)
async def db_session_override():
    """Ensure tests use an isolated NullPool engine to avoid cross-loop connection sharing."""
    test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    test_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async def _get_test_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)
    await test_engine.dispose()


@pytest.fixture
def mock_health_healthy():
    with (
        patch(
            "apps.api.src.api.v1.endpoints.health.check_database_health", new_callable=AsyncMock
        ) as mock_db,
        patch(
            "apps.api.src.api.v1.endpoints.health.check_redis_health", new_callable=AsyncMock
        ) as mock_redis,
    ):
        mock_db.return_value = {
            "status": "healthy",
            "connected": True,
            "pgvector_installed": True,
        }
        mock_redis.return_value = {
            "status": "healthy",
            "connected": True,
        }
        yield mock_db, mock_redis


@pytest.fixture
def mock_health_unhealthy():
    with (
        patch(
            "apps.api.src.api.v1.endpoints.health.check_database_health", new_callable=AsyncMock
        ) as mock_db,
        patch(
            "apps.api.src.api.v1.endpoints.health.check_redis_health", new_callable=AsyncMock
        ) as mock_redis,
    ):
        mock_db.return_value = {
            "status": "unhealthy",
            "connected": False,
            "pgvector_installed": False,
            "error": "Connection refused",
        }
        mock_redis.return_value = {
            "status": "unhealthy",
            "connected": False,
            "error": "Connection refused",
        }
        yield mock_db, mock_redis


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
