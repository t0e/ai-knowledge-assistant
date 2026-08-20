import logging
import uuid

from apps.api.src.core.config import settings
from apps.api.src.core.database import get_db
from apps.api.src.core.exceptions import AppException
from apps.api.src.core.redis import get_redis_client
from apps.api.src.core.security import decode_access_token
from apps.api.src.models.user import User
from apps.api.src.services.auth_service import AuthService
from fastapi import Depends, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("ai_knowledge_assistant.dependencies")

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,
)


def extract_token_from_request(
    request: Request,
    header_token: str | None = Depends(oauth2_scheme),
) -> str | None:
    """Extract token from HttpOnly cookie or Authorization Bearer header."""
    # Check HttpOnly cookie first
    cookie_token = request.cookies.get(settings.COOKIE_NAME)
    if cookie_token:
        return cookie_token
    # Fallback to Authorization header
    if header_token:
        return header_token
    return None


async def get_current_user_optional(
    token: str | None = Depends(extract_token_from_request),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Retrieve user if token is present and valid, otherwise None."""
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    user_id_str: str | None = payload.get("sub")
    if not user_id_str:
        return None

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        return None

    user = await AuthService.get_user_by_id(db, user_uuid)
    return user


async def get_current_user(
    current_user: User | None = Depends(get_current_user_optional),
) -> User:
    """Enforce authenticated user requirement."""
    if not current_user:
        raise AppException(
            title="Unauthorized",
            detail="Authentication credentials were not provided or are invalid.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_type="https://api.knowledgeassistant.dev/errors/unauthorized",
        )
    if not current_user.is_active:
        raise AppException(
            title="Account Inactive",
            detail="This account has been disabled.",
            status_code=status.HTTP_403_FORBIDDEN,
            error_type="https://api.knowledgeassistant.dev/errors/account-inactive",
        )
    return current_user


# Alias for dependency clarity
require_authenticated_user = get_current_user

__all__ = [
    "get_db",
    "get_redis_client",
    "get_current_user",
    "get_current_user_optional",
    "require_authenticated_user",
]
