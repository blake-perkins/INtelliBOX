"""add settings table

Revision ID: 003
Revises: 002
Create Date: 2026-02-16 19:30:00.000000

"""
from datetime import datetime

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create settings table for configurable priority rules."""
    op.create_table(
        'settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_settings_key', 'settings', ['key'], unique=True)

    # Insert default settings using portable bulk_insert (works on both SQLite and PostgreSQL)
    settings_table = sa.table(
        'settings',
        sa.column('key', sa.String),
        sa.column('value', sa.Text),
        sa.column('description', sa.Text),
        sa.column('updated_at', sa.DateTime),
    )
    now = datetime.utcnow()
    op.bulk_insert(settings_table, [
        {
            'key': 'priority_days_threshold',
            'value': '5',
            'description': 'Number of days: if due date is within this many days, priority is high',
            'updated_at': now,
        },
        {
            'key': 'priority_high_senders',
            'value': '[]',
            'description': 'JSON array of email addresses/domains that trigger high priority',
            'updated_at': now,
        },
        {
            'key': 'priority_high_keywords',
            'value': '[]',
            'description': 'JSON array of keywords in subject/body that trigger high priority',
            'updated_at': now,
        },
        {
            'key': 'priority_default',
            'value': 'medium',
            'description': 'Default priority if no other rules match (high/medium/low)',
            'updated_at': now,
        },
    ])


def downgrade() -> None:
    """Remove settings table."""
    op.drop_index('ix_settings_key', table_name='settings')
    op.drop_table('settings')
