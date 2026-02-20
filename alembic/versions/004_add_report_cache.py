"""add report cache

Revision ID: 004
Revises: 003
Create Date: 2026-02-16

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add report_cache table for caching generated reports."""
    op.create_table(
        'report_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('report_data', sa.Text(), nullable=False),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_report_cache_generated_at'), 'report_cache', ['generated_at'], unique=False)


def downgrade() -> None:
    """Remove report_cache table."""
    op.drop_index(op.f('ix_report_cache_generated_at'), table_name='report_cache')
    op.drop_table('report_cache')
