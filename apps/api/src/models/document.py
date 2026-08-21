import uuid
from typing import TYPE_CHECKING

from apps.api.src.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from apps.api.src.models.document_chunk import DocumentChunk
    from apps.api.src.models.user import User


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Document database entity representing an uploaded knowledge source."""

    __tablename__ = "documents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    storage_path: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    source_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="uploaded",
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="documents",
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentChunk.chunk_index",
    )

    def __repr__(self) -> str:
        return (
            f"<Document id={self.id} user_id={self.user_id} name={self.name} status={self.status}>"
        )
