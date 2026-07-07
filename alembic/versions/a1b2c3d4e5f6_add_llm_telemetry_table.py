"""Add llm_telemetry table

Revision ID: a1b2c3d4e5f6
Revises: 10e6f9024936
Create Date: 2026-07-07 09:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str | Sequence[str] | None = '10e6f9024936'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create llm_telemetry table for persistent LLM execution telemetry."""
    op.create_table(
        'llm_telemetry',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('operation', sa.String(length=255), nullable=True),
        sa.Column('task_id', sa.String(length=50), nullable=True),
        sa.Column('request_id', sa.String(length=50), nullable=True),
        sa.Column('correlation_id', sa.String(length=50), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('estimated_cost', sa.Float(), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_llm_telemetry_provider', 'llm_telemetry', ['provider'])
    op.create_index('idx_llm_telemetry_timestamp', 'llm_telemetry', ['timestamp'])
    op.create_index('idx_llm_telemetry_status', 'llm_telemetry', ['status'])


def downgrade() -> None:
    """Drop llm_telemetry table."""
    op.drop_index('idx_llm_telemetry_status', table_name='llm_telemetry')
    op.drop_index('idx_llm_telemetry_timestamp', table_name='llm_telemetry')
    op.drop_index('idx_llm_telemetry_provider', table_name='llm_telemetry')
    op.drop_table('llm_telemetry')
