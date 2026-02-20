"""add knowledge_documents table

Revision ID: 007
Revises: 006
Create Date: 2026-02-17

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add knowledge_documents table for program document storage."""
    op.create_table(
        'knowledge_documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(500), nullable=False),
        sa.Column('file_type', sa.String(10), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('extraction_status', sa.String(20), nullable=False, server_default='success'),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_knowledge_documents_uploaded_at'),
        'knowledge_documents',
        ['uploaded_at'],
        unique=False
    )


def downgrade() -> None:
    """Remove knowledge_documents table."""
    op.drop_index(op.f('ix_knowledge_documents_uploaded_at'), table_name='knowledge_documents')
    op.drop_table('knowledge_documents')
