"""price alerts

Push-Meldungen bei starken Kursbewegungen und erreichten Zielkursen:
- push_subscription bekommt zwei Schalter (price_moves, watchlist); schon angemeldete
  Geräte bekommen beide eingeschaltet, wie neue Geräte auch
- watchlist bekommt einen Zielkurs in Euro (target_price), ob er von unten oder oben
  erreicht werden soll (target_direction: 'above' / 'below') und wann er erreicht wurde
  (target_hit_at)
An bestehenden Daten ändert sich nichts.

Revision ID: 0012_price_alerts
Revises: 0011_push
Create Date: 2026-11-12 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0012_price_alerts'
down_revision = '0011_push'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('push_subscription', sa.Column('price_moves', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('push_subscription', sa.Column('watchlist', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('watchlist', sa.Column('target_price', sa.Float(), nullable=True))
    op.add_column('watchlist', sa.Column('target_direction', sa.String(length=5), nullable=True))
    op.add_column('watchlist', sa.Column('target_hit_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('watchlist') as batch_op:
        batch_op.drop_column('target_hit_at')
        batch_op.drop_column('target_direction')
        batch_op.drop_column('target_price')
    with op.batch_alter_table('push_subscription') as batch_op:
        batch_op.drop_column('watchlist')
        batch_op.drop_column('price_moves')
