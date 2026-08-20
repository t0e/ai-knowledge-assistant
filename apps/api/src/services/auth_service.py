import logging
import uuid

from apps.api.src.core.exceptions import AppException
from apps.api.src.core.security import hash_password, verify_password
from apps.api.src.models.user import User
from apps.api.src.schemas.auth import UserLoginRequest, UserRegisterRequest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("ai_knowledge_assistant.auth")


class AuthService:
    """Service handling user registration, authentication, and retrieval."""

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
        """Fetch user by primary UUID."""
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
        """Fetch user by normalized email address."""
        stmt = select(User).where(User.email == email.strip().lower())
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def register_user(
        db: AsyncSession,
        register_data: UserRegisterRequest,
    ) -> User:
        """Register a new user, ensuring email uniqueness and password hashing."""
        existing_user = await AuthService.get_user_by_email(db, register_data.email)
        if existing_user:
            logger.warning(
                f"Registration attempt for already registered email: {register_data.email}"
            )
            raise AppException(
                title="Email Already Registered",
                detail="An account with this email address already exists.",
                status_code=409,
                error_type="https://api.knowledgeassistant.dev/errors/email-conflict",
            )

        hashed_pwd = hash_password(register_data.password)
        new_user = User(
            email=register_data.email,
            password_hash=hashed_pwd,
            is_active=True,
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        logger.info(f"Successfully registered user with id={new_user.id}")
        return new_user

    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        login_data: UserLoginRequest,
    ) -> User:
        """Authenticate user credentials using constant-time hash comparison."""
        user = await AuthService.get_user_by_email(db, login_data.email)
        if not user or not verify_password(login_data.password, user.password_hash):
            logger.warning(f"Failed authentication attempt for email: {login_data.email}")
            raise AppException(
                title="Authentication Failed",
                detail="Invalid email or password.",
                status_code=401,
                error_type="https://api.knowledgeassistant.dev/errors/unauthorized",
            )

        if not user.is_active:
            logger.warning(f"Authentication attempt on inactive user id={user.id}")
            raise AppException(
                title="Account Inactive",
                detail="This account has been disabled.",
                status_code=403,
                error_type="https://api.knowledgeassistant.dev/errors/account-inactive",
            )

        logger.info(f"User id={user.id} successfully authenticated.")
        return user
