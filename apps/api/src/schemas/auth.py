from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    """Payload for user registration."""

    email: EmailStr = Field(..., examples=["user@example.com"])
    password: str = Field(..., min_length=8, max_length=128, examples=["SecurePass123!"])

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        return v


class UserLoginRequest(BaseModel):
    """Payload for user authentication."""

    email: EmailStr = Field(..., examples=["user@example.com"])
    password: str = Field(..., min_length=1, max_length=128, examples=["SecurePass123!"])

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class MessageResponse(BaseModel):
    """Generic status/message response."""

    message: str = Field(..., examples=["Action completed successfully."])
