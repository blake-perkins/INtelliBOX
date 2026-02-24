"""add api_usage_log table

Revision ID: 012
Revises: 011
Create Date: 2026-02-23

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add api_usage_log table for tracking OpenAI API usage telemetry."""
    op.create_table(
        'api_usage_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('call_type', sa.String(50), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('latency_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='success'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('email_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['email_id'], ['emails.id'], ondelete='SET NULL'),
    )
    op.create_index(op.f('ix_api_usage_log_call_type'), 'api_usage_log', ['call_type'])
    op.create_index(op.f('ix_api_usage_log_email_id'), 'api_usage_log', ['email_id'])
    op.create_index(op.f('ix_api_usage_log_created_at'), 'api_usage_log', ['created_at'])


def downgrade() -> None:
    """Remove api_usage_log table."""
    op.drop_index(op.f('ix_api_usage_log_created_at'), table_name='api_usage_log')
    op.drop_index(op.f('ix_api_usage_log_email_id'), table_name='api_usage_log')
    op.drop_index(op.f('ix_api_usage_log_call_type'), table_name='api_usage_log')
    op.drop_table('api_usage_log')
