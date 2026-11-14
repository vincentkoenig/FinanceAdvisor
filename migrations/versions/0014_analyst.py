"""analyst signals

Wöchentliche Einschätzungen des Analysten: analyst_signal speichert pro Nutzer, Wert
und Lauf die Einschätzung samt Kurs und Kennzahlen, damit sich später messen lässt,
wie sie sich bewährt hat. Neue Tabelle, an bestehenden Daten ändert sich nichts.

Revision ID: 0014_analyst
Revises: 0013_insight_news
Create Date: 2026-11-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0014_analyst'
down_revision = '0013_insight_news'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'analyst_signal',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('run_date', sa.Date(), nullable=False),
        sa.Column('kind', sa.String(length=10), nullable=False),
        sa.Column('stance', sa.String(length=20), nullable=False),
        sa.Column('confidence', sa.String(length=10), nullable=False),
        sa.Column('reasoning', sa.Text(), nullable=False),
        sa.Column('invalidation', sa.Text(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('indicators', sa.Text(), nullable=True),
        sa.Column('model', sa.String(length=60), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['asset.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'asset_id', 'run_date'),
    )


def downgrade():
    op.drop_table('analyst_signal')
