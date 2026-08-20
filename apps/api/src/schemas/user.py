import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserResponse(BaseModel):
    """User representation returned to API consumers."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., examples=["123e4567-e89b-12d3-a456-426614174000"])
    email: EmailStr = Field(..., examples=["user@example.com"])
    is_active: bool = Field(..., examples=[True])
    created_at: datetime
    updated_at: datetime
