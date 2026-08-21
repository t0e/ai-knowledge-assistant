"""007_add_source_url_to_documents

Revision ID: 007_add_source_url_to_documents
Revises: 006_conversations_messages
Create Date: 2026-08-20 22:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "007_add_source_url_to_documents"
down_revision: str | None = "006_conversations_messages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add source_url column to documents table
    op.add_column(
        "documents",
        sa.Column("source_url", sa.String(length=2048), nullable=True),
    )

    # 2. Make storage_path nullable to support remote URL sources
    op.alter_column(
        "documents",
        "storage_path",
        existing_type=sa.String(length=512),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "documents",
        "storage_path",
        existing_type=sa.String(length=512),
        nullable=False,
    )
    op.drop_column("documents", "source_url")
