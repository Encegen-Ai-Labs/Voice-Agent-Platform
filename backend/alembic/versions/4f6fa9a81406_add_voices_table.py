"""add voices table

Revision ID: 4f6fa9a81406
Revises: 1c964e8515e5
Create Date: 2026-07-07 12:58:47.029611
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "4f6fa9a81406"
down_revision: Union[str, Sequence[str], None] = "1c964e8515e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "voices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_voice_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("gender", sa.String(), nullable=True),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_voices_provider_voice_id",
        "voices",
        ["provider_voice_id"],
        unique=True,
    )

    with op.batch_alter_table("usage_records") as batch_op:
        batch_op.alter_column(
            "total_minutes",
            existing_type=sa.Integer(),
            type_=sa.Float(),
            existing_nullable=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("usage_records") as batch_op:
        batch_op.alter_column(
            "total_minutes",
            existing_type=sa.Float(),
            type_=sa.Integer(),
            existing_nullable=False,
        )

    op.drop_index("ix_voices_provider_voice_id", table_name="voices")
    op.drop_table("voices")