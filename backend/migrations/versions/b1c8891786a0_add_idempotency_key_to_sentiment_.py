"""add idempotency key to sentiment analyses

Revision ID: b1c8891786a0
Revises: 36ffaba3b9b4
Create Date: 2026-08-19 17:08:17.592010

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c8891786a0'
down_revision: Union[str, Sequence[str], None] = '36ffaba3b9b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Uses batch mode: SQLite (used for local dev/tests, see migrations/env.py's
    fallback) can't ALTER a table to add a constraint directly -- only
    Postgres (the real production target) can. Batch mode does the
    copy-recreate-swap SQLite needs under the hood while still emitting a
    plain ALTER TABLE on Postgres, so the same migration file works against
    both.
    """
    with op.batch_alter_table('sentiment_analyses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('idempotency_key', sa.String(length=64), nullable=True))
        batch_op.create_index(batch_op.f('ix_sentiment_analyses_idempotency_key'), ['idempotency_key'], unique=False)
        batch_op.create_unique_constraint('ux_analyses_idempotency_key', ['idempotency_key'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('sentiment_analyses', schema=None) as batch_op:
        batch_op.drop_constraint('ux_analyses_idempotency_key', type_='unique')
        batch_op.drop_index(batch_op.f('ix_sentiment_analyses_idempotency_key'))
        batch_op.drop_column('idempotency_key')
