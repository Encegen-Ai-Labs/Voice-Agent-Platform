"""add webhook url and nullable phone number agent

Revision ID: 04d5215b1497
Revises: d385c95d0f7c
Create Date: 2026-05-06 16:10:46.531897

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "04d5215b1497"
down_revision: Union[str, Sequence[str], None] = "d385c95d0f7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    with op.batch_alter_table("phone_numbers") as batch_op:
        batch_op.alter_column(
            "agent_id",
            existing_type=sa.Uuid(),
            nullable=True
        )


def downgrade() -> None:

    with op.batch_alter_table("phone_numbers") as batch_op:
        batch_op.alter_column(
            "agent_id",
            existing_type=sa.Uuid(),
            nullable=False
        )