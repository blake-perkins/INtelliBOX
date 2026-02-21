"""add audit_log table

Revision ID: 011
Revises: 010
Create Date: 2026-02-20

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add audit_log table for tracking user write operations."""
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user', sa.String(150), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_log_user'), 'audit_log', ['user'])
    op.create_index(op.f('ix_audit_log_action'), 'audit_log', ['action'])
    op.create_index(op.f('ix_audit_log_resource_type'), 'audit_log', ['resource_type'])
    op.create_index(op.f('ix_audit_log_created_at'), 'audit_log', ['created_at'])


def downgrade() -> None:
    """Remove audit_log table."""
    op.drop_index(op.f('ix_audit_log_created_at'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_resource_type'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_action'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_user'), table_name='audit_log')
    op.drop_table('audit_log')
