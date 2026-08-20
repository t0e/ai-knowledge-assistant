import logging

from apps.api.src.api.dependencies import get_current_user, get_db
from apps.api.src.core.config import settings
from apps.api.src.core.security import create_access_token
from apps.api.src.models.user import User
from apps.api.src.schemas.auth import MessageResponse, UserLoginRequest, UserRegisterRequest
from apps.api.src.schemas.user import UserResponse
from apps.api.src.services.auth_service import AuthService
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("ai_knowledge_assistant.api.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _set_auth_cookie(response: Response, token: str) -> None:
    """Set secure HttpOnly authentication cookie."""
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    """Clear authentication cookie upon logout."""
    response.delete_cookie(
        key=settings.COOKIE_NAME,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path="/",
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register New User Account",
    description="Validates email and password, creates the user with hashed credentials, and establishes a secure session.",
)
async def register(
    payload: UserRegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await AuthService.register_user(db, payload)
    token = create_access_token(subject=str(user.id), email=user.email)
    _set_auth_cookie(response, token)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate User",
    description="Validates credentials and sets a secure HttpOnly session cookie without revealing account existence on failure.",
)
async def login(
    payload: UserLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await AuthService.authenticate_user(db, payload)
    token = create_access_token(subject=str(user.id), email=user.email)
    _set_auth_cookie(response, token)
    return UserResponse.model_validate(user)


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="User Logout",
    description="Clears the HttpOnly authentication session cookie.",
)
async def logout(response: Response) -> MessageResponse:
    _clear_auth_cookie(response)
    return MessageResponse(message="Successfully logged out.")


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current Authenticated User",
    description="Returns profile metadata for the authenticated user based on session cookie or token.",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)
