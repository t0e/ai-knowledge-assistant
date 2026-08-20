import logging
from collections.abc import AsyncGenerator
from typing import Any

from apps.api.src.core.config import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for obtaining an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_pgvector_extension() -> bool:
    """Ensure the pgvector extension is enabled in PostgreSQL."""
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            logger.info("pgvector extension initialized successfully.")
            return True
    except Exception as e:
        logger.warning(f"Could not auto-create pgvector extension on startup: {e}")
        return False


async def check_database_health() -> dict[str, Any]:
    """Check database connectivity and pgvector extension availability."""
    try:
        async with AsyncSessionLocal() as session:
            # Check connectivity
            res = await session.execute(text("SELECT 1"))
            connected = res.scalar() == 1

            # Check pgvector extension
            ext_res = await session.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector';")
            )
            has_pgvector = ext_res.scalar() is not None

            return {
                "status": "healthy" if (connected and has_pgvector) else "degraded",
                "connected": connected,
                "pgvector_installed": has_pgvector,
            }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "connected": False,
            "pgvector_installed": False,
            "error": str(e),
        }
