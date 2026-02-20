"""Initial schema.

Revision ID: 001
Revises:
Create Date: 2026-02-16 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""

    # Create emails table
    op.create_table(
        'emails',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('message_id', sa.String(length=255), nullable=False),
        sa.Column('subject', sa.Text(), nullable=False),
        sa.Column('from_address', sa.String(length=255), nullable=False),
        sa.Column('from_name', sa.String(length=255), nullable=True),
        sa.Column('to_addresses', sa.Text(), nullable=False),
        sa.Column('cc_addresses', sa.Text(), nullable=True),
        sa.Column('received_date', sa.DateTime(), nullable=False),
        sa.Column('body_text', sa.Text(), nullable=True),
        sa.Column('body_html', sa.Text(), nullable=True),
        sa.Column('raw_eml_path', sa.String(length=500), nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('message_id')
    )
    op.create_index('idx_emails_message_id', 'emails', ['message_id'])
    op.create_index('idx_emails_processed', 'emails', ['processed'])
    op.create_index('idx_emails_received_date', 'emails', ['received_date'])

    # Create actions table
    op.create_table(
        'actions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('priority', sa.String(length=10), nullable=True),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('raw_ai_response', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("priority IN ('high', 'medium', 'low')", name='check_priority'),
        sa.ForeignKeyConstraint(['email_id'], ['emails.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_actions_email_id', 'actions', ['email_id'])
    op.create_index('idx_actions_priority', 'actions', ['priority'])
    op.create_index('idx_actions_due_date', 'actions', ['due_date'])

    # Create assignments table
    op.create_table(
        'assignments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('action_id', sa.Integer(), nullable=False),
        sa.Column('assigned_to', sa.String(length=255), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='assigned'),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('assigned', 'in_progress', 'completed')",
            name='check_status'
        ),
        sa.ForeignKeyConstraint(['action_id'], ['actions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_assignments_action_id', 'assignments', ['action_id'])
    op.create_index('idx_assignments_status', 'assignments', ['status'])

    # Create processing_log table
    op.create_table(
        'processing_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email_id', sa.Integer(), nullable=True),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('event_metadata', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('success', 'failure', 'warning')",
            name='check_log_status'
        ),
        sa.ForeignKeyConstraint(['email_id'], ['emails.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_log_event_type', 'processing_log', ['event_type'])
    op.create_index('idx_log_created_at', 'processing_log', ['created_at'])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_index('idx_log_created_at', 'processing_log')
    op.drop_index('idx_log_event_type', 'processing_log')
    op.drop_table('processing_log')

    op.drop_index('idx_assignments_status', 'assignments')
    op.drop_index('idx_assignments_action_id', 'assignments')
    op.drop_table('assignments')

    op.drop_index('idx_actions_due_date', 'actions')
    op.drop_index('idx_actions_priority', 'actions')
    op.drop_index('idx_actions_email_id', 'actions')
    op.drop_table('actions')

    op.drop_index('idx_emails_received_date', 'emails')
    op.drop_index('idx_emails_processed', 'emails')
    op.drop_index('idx_emails_message_id', 'emails')
    op.drop_table('emails')
