"""005_add_embeddings

Revision ID: 005_add_embeddings
Revises: 004_create_document_chunks_table
Create Date: 2026-08-20 19:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "005_add_embeddings"
down_revision: str | None = "004_create_document_chunks_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add vector column (1536 dimensions for text-embedding-3-small)
    op.add_column(
        "document_chunks",
        sa.Column("embedding", Vector(1536), nullable=True),
    )

    # 2. Create HNSW index using cosine distance operator class
    op.create_index(
        "ix_document_chunks_embedding_hnsw",
        "document_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_embedding_hnsw", table_name="document_chunks")
    op.drop_column("document_chunks", "embedding")
