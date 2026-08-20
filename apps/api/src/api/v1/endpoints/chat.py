from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.get("/sessions", summary="List Chat Sessions Placeholder")
async def list_sessions() -> dict[str, Any]:
    return {
        "message": "Chat API placeholder (will be implemented in Phase 3)",
        "sessions": [],
    }
