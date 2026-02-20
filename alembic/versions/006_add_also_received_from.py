"""add also_received_from to emails

Revision ID: 006
Revises: 005
Create Date: 2026-02-17

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add also_received_from column to emails table."""
    op.add_column('emails', sa.Column('also_received_from', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove also_received_from column."""
    op.drop_column('emails', 'also_received_from')
