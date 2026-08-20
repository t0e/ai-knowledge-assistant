"""001_initial_pgvector

Revision ID: 001_initial_pgvector
Revises:
Create Date: 2026-08-20 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "001_initial_pgvector"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Ensure pgvector extension is created in the database
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector CASCADE;")
