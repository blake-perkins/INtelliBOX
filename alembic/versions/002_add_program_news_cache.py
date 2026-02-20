"""Add program news cache table

Revision ID: 002
Revises: 001
Create Date: 2026-02-16 15:11:00

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('program_news_cache',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('days_covered', sa.Integer(), nullable=False),
    sa.Column('email_count', sa.Integer(), nullable=False),
    sa.Column('latest_email_date', sa.DateTime(), nullable=True),
    sa.Column('generated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_program_news_cache_generated_at', 'program_news_cache', ['generated_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_program_news_cache_generated_at', table_name='program_news_cache')
    op.drop_table('program_news_cache')
