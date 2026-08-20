import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("ai_knowledge_assistant.exceptions")


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        title: str,
        detail: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_type: str = "https://api.knowledgeassistant.dev/errors/internal",
        extra: dict[str, Any] | None = None,
    ):
        super().__init__(detail)
        self.title = title
        self.detail = detail
        self.status_code = status_code
        self.error_type = error_type
        self.extra = extra or {}


class NotFoundException(AppException):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            title="Resource Not Found",
            detail=f"{resource} with identifier '{identifier}' was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            error_type="https://api.knowledgeassistant.dev/errors/not-found",
        )


class ValidationException(AppException):
    def __init__(self, detail: str, extra: dict[str, Any] | None = None):
        super().__init__(
            title="Validation Error",
            detail=detail,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_type="https://api.knowledgeassistant.dev/errors/validation-error",
            extra=extra,
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers compliant with RFC 7807 problem details."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": exc.error_type,
                "title": exc.title,
                "status": exc.status_code,
                "detail": exc.detail,
                "instance": request.url.path,
                "timestamp": datetime.now(UTC).isoformat(),
                **exc.extra,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "type": "https://api.knowledgeassistant.dev/errors/validation-error",
                "title": "Unprocessable Entity",
                "status": 422,
                "detail": "Request payload failed schema validation.",
                "instance": request.url.path,
                "timestamp": datetime.now(UTC).isoformat(),
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            f"Unhandled exception during request processing: {request.method} {request.url.path} - {exc}",
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "type": "https://api.knowledgeassistant.dev/errors/internal-server-error",
                "title": "Internal Server Error",
                "status": 500,
                "detail": "An unexpected internal error occurred. Please try again later.",
                "instance": request.url.path,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
