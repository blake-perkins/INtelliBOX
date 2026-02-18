"""add knowledge_chunks table for embedding storage

Revision ID: 008
Revises: 007
Create Date: 2026-02-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add knowledge_chunks table for storing document chunk embeddings."""
    op.create_table(
        'knowledge_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('embedding', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['knowledge_documents.id'], ondelete='CASCADE'),
    )
    op.create_index(
        op.f('ix_knowledge_chunks_document_id'),
        'knowledge_chunks',
        ['document_id'],
        unique=False
    )


def downgrade() -> None:
    """Remove knowledge_chunks table."""
    op.drop_index(op.f('ix_knowledge_chunks_document_id'), table_name='knowledge_chunks')
    op.drop_table('knowledge_chunks')
