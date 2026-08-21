import logging
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from apps.api.src.api.v1.router import api_router
from apps.api.src.core.config import settings
from apps.api.src.core.database import engine, init_pgvector_extension
from apps.api.src.core.exceptions import register_exception_handlers
from apps.api.src.core.redis import close_redis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ai_knowledge_assistant")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION} [{settings.ENVIRONMENT}]")

    # Check/init pgvector extension on startup
    await init_pgvector_extension()

    yield

    logger.info("Shutting down application and releasing resources...")
    await close_redis()
    await engine.dispose()
    logger.info("Shutdown complete.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Production-grade AI Knowledge Assistant with RAG, pgvector, and Next.js",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Exception handlers
register_exception_handlers(app)

# CORS Middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Request ID & Timing Correlation Middleware
@app.middleware("http")
async def request_correlation_and_timing_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id

    start_time = time.perf_counter()
    try:
        response = await call_next(request)
        process_time_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time_ms:.2f}ms"

        # Privacy-safe structured access log
        if not request.url.path.endswith("/health"):
            logger.info(
                f"HTTP {request.method} {request.url.path} -> {response.status_code} "
                f"({process_time_ms:.2f}ms) [request_id={request_id}]"
            )
        return response
    except Exception as exc:
        process_time_ms = (time.perf_counter() - start_time) * 1000
        logger.error(
            f"HTTP {request.method} {request.url.path} FAILED: {exc} "
            f"({process_time_ms:.2f}ms) [request_id={request_id}]"
        )
        raise exc


# Include API v1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"])
async def root():
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
        "api_v1": f"{settings.API_V1_STR}",
        "health": f"{settings.API_V1_STR}/health",
    }
