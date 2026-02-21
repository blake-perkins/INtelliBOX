"""add in_progress to assignment status CHECK constraint

Revision ID: 010
Revises: 009
Create Date: 2026-02-20

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Widen assignments.status CHECK to include 'in_progress'."""
    # SQLite cannot ALTER CHECK constraints — batch mode recreates the table.
    # PostgreSQL can drop + add constraints directly.
    with op.batch_alter_table("assignments") as batch_op:
        batch_op.drop_constraint("check_status", type_="check")
        batch_op.create_check_constraint(
            "check_status",
            "status IN ('assigned', 'in_progress', 'completed')",
        )


def downgrade() -> None:
    """Revert assignments.status CHECK to original two-value constraint."""
    with op.batch_alter_table("assignments") as batch_op:
        batch_op.drop_constraint("check_status", type_="check")
        batch_op.create_check_constraint(
            "check_status",
            "status IN ('assigned', 'completed')",
        )
