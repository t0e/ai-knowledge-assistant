import uuid
from typing import TYPE_CHECKING

from apps.api.src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from apps.api.src.models.message import Message
    from apps.api.src.models.user import User


class Conversation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Conversation entity grouping messages for a specific user."""

    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="New Conversation",
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="conversations",
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at.asc()",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} user_id={self.user_id} title='{self.title[:30]}'>"
