"""Add column_business table for column intelligence

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-10 12:45:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: str | Sequence[str] | None = 'a1b2c3d4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create column_business table for schema column intelligence."""
    op.create_table(
        'column_business',
        sa.Column('fingerprint', sa.String(length=64), nullable=False),
        sa.Column('business_logic_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('fingerprint'),
    )


def downgrade() -> None:
    """Drop column_business table."""
    op.drop_table('column_business')
