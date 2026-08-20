from datetime import UTC, datetime
from typing import Any

from apps.api.src.core.config import settings
from apps.api.src.core.database import check_database_health
from apps.api.src.core.redis import check_redis_health
from apps.api.src.schemas.health import (
    DatabaseHealth,
    HealthResponse,
    ProbeResponse,
    ServiceComponentHealth,
)
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/health", tags=["Health & Diagnostics"])


@router.get(
    "",
    response_model=HealthResponse,
    summary="Comprehensive Service Health",
    description="Inspects database connectivity, pgvector extension presence, and Redis connection.",
)
async def health_check() -> Any:
    db_health = await check_database_health()
    redis_health = await check_redis_health()

    overall_healthy = (
        db_health.get("connected", False)
        and db_health.get("pgvector_installed", False)
        and redis_health.get("connected", False)
    )

    data = HealthResponse(
        status="healthy" if overall_healthy else "degraded",
        project_name=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(UTC),
        database=DatabaseHealth(**db_health),
        redis=ServiceComponentHealth(**redis_health),
    )

    status_code = status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=data.model_dump(mode="json"))


@router.get(
    "/liveness",
    response_model=ProbeResponse,
    summary="Liveness Probe",
    description="Verifies the API server process is alive.",
)
async def liveness_probe() -> ProbeResponse:
    return ProbeResponse(status="ok", timestamp=datetime.now(UTC))


@router.get(
    "/readiness",
    response_model=ProbeResponse,
    summary="Readiness Probe",
    description="Verifies the API server is ready to accept incoming traffic.",
)
async def readiness_probe() -> Any:
    db_health = await check_database_health()
    if not db_health.get("connected", False):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "reason": "Database connection failed",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
    return ProbeResponse(status="ready", timestamp=datetime.now(UTC))
