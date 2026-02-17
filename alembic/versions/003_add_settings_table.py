"""add settings table

Revision ID: 003
Revises: 002
Create Date: 2026-02-16 19:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


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

    # Insert default settings
    op.execute("""
        INSERT INTO settings (key, value, description, updated_at) VALUES
        ('priority_days_threshold', '5', 'Number of days: if due date is within this many days, priority is high', datetime('now')),
        ('priority_high_senders', '[]', 'JSON array of email addresses/domains that trigger high priority', datetime('now')),
        ('priority_high_keywords', '[]', 'JSON array of keywords in subject/body that trigger high priority', datetime('now')),
        ('priority_default', 'medium', 'Default priority if no other rules match (high/medium/low)', datetime('now'))
    """)


def downgrade() -> None:
    """Remove settings table."""
    op.drop_index('ix_settings_key', table_name='settings')
    op.drop_table('settings')
