"""add twilio_call_sid to calls"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "2e8bf80022ad"
down_revision: Union[str, Sequence[str], None] = "40a80aeb061e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = [
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("calls")
    ]

    if "twilio_call_sid" not in columns:
        op.add_column(
            "calls",
            sa.Column("twilio_call_sid", sa.String(), nullable=True),
        )

    op.create_index(
        "uq_calls_twilio_call_sid",
        "calls",
        ["twilio_call_sid"],
        unique=True,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_calls_twilio_call_sid",
        table_name="calls",
        if_exists=True,
    )

    columns = [
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("calls")
    ]

    if "twilio_call_sid" in columns:
        with op.batch_alter_table("calls") as batch_op:
            batch_op.drop_column("twilio_call_sid")