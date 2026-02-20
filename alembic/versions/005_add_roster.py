"""add roster table

Revision ID: 005
Revises: 004
Create Date: 2026-02-16

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add roster table for program team members."""
    op.create_table(
        'roster',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_roster_email')
    )
    op.create_index(op.f('ix_roster_email'), 'roster', ['email'], unique=True)


def downgrade() -> None:
    """Remove roster table."""
    op.drop_index(op.f('ix_roster_email'), table_name='roster')
    op.drop_table('roster')
