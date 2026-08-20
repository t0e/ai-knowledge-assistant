import logging

import pytest
import pytest_asyncio
from apps.api.src.core.exceptions import (
    AppException,
    NotFoundException,
    register_exception_handlers,
)
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field


@pytest.fixture
def test_app():
    """Create an isolated test FastAPI application with registered exception handlers."""
    app = FastAPI()
    register_exception_handlers(app)
    router = APIRouter()

    class SamplePayload(BaseModel):
        name: str = Field(..., min_length=3)
        count: int = Field(..., gt=0)

    @router.get("/trigger-unexpected")
    async def trigger_unexpected():
        # Simulate an internal crash with sensitive database connection info
        raise RuntimeError("CRITICAL: Database password 'secret_pass_123' at /var/lib/db failed.")

    @router.get("/trigger-not-found")
    async def trigger_not_found():
        raise NotFoundException(resource="Document", identifier="doc_abc123")

    @router.get("/trigger-custom-app-exception")
    async def trigger_custom_app_exception():
        raise AppException(
            title="Custom Domain Error",
            detail="A custom business logic rule failed.",
            status_code=400,
            error_type="https://api.knowledgeassistant.dev/errors/custom",
            extra={"extra_field": "extra_value"},
        )

    @router.post("/trigger-validation")
    async def trigger_validation(payload: SamplePayload):
        return {"received": payload.model_dump()}

    app.include_router(router)
    return app


@pytest_asyncio.fixture
async def test_client(test_app) -> AsyncClient:
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_unexpected_exception_returns_sanitized_500(test_client: AsyncClient, caplog):
    """Verify that an unexpected exception produces a sanitized RFC 7807 500 response and logs trace."""
    with caplog.at_level(logging.ERROR, logger="ai_knowledge_assistant.exceptions"):
        response = await test_client.get("/trigger-unexpected")

    assert response.status_code == 500
    data = response.json()

    # RFC 7807 structure checks
    assert data["type"] == "https://api.knowledgeassistant.dev/errors/internal-server-error"
    assert data["title"] == "Internal Server Error"
    assert data["status"] == 500
    assert data["detail"] == "An unexpected internal error occurred. Please try again later."
    assert data["instance"] == "/trigger-unexpected"
    assert "timestamp" in data

    # Security check: Internal details, trace, and secrets must NEVER be present in response
    assert "secret_pass_123" not in response.text
    assert "RuntimeError" not in response.text
    assert "/var/lib/db" not in response.text

    # Logging verification: Traceback must be recorded in application logs
    assert len(caplog.records) >= 1
    log_record = caplog.records[0]
    assert log_record.levelname == "ERROR"
    assert "secret_pass_123" in log_record.message
    assert log_record.exc_info is not None


@pytest.mark.asyncio
async def test_not_found_app_exception_behavior_preserved(test_client: AsyncClient):
    """Verify that specific AppException (NotFoundException) is not intercepted by 500 handler."""
    response = await test_client.get("/trigger-not-found")
    assert response.status_code == 404
    data = response.json()

    assert data["type"] == "https://api.knowledgeassistant.dev/errors/not-found"
    assert data["title"] == "Resource Not Found"
    assert data["status"] == 404
    assert data["detail"] == "Document with identifier 'doc_abc123' was not found."
    assert data["instance"] == "/trigger-not-found"


@pytest.mark.asyncio
async def test_custom_app_exception_with_extra_fields(test_client: AsyncClient):
    """Verify custom AppException with status code and extra metadata is preserved."""
    response = await test_client.get("/trigger-custom-app-exception")
    assert response.status_code == 400
    data = response.json()

    assert data["type"] == "https://api.knowledgeassistant.dev/errors/custom"
    assert data["title"] == "Custom Domain Error"
    assert data["status"] == 400
    assert data["detail"] == "A custom business logic rule failed."
    assert data["extra_field"] == "extra_value"


@pytest.mark.asyncio
async def test_request_validation_error_behavior_preserved(test_client: AsyncClient):
    """Verify that FastAPI schema validation errors return 422 with detailed field errors."""
    response = await test_client.post("/trigger-validation", json={"name": "a", "count": -5})
    assert response.status_code == 422
    data = response.json()

    assert data["type"] == "https://api.knowledgeassistant.dev/errors/validation-error"
    assert data["title"] == "Unprocessable Entity"
    assert data["status"] == 422
    assert "errors" in data
    assert len(data["errors"]) >= 1
