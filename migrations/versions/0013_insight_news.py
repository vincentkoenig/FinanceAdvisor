"""daily insight news

Das Tages-Update bekommt die News zu den eigenen Depotpositionen: daily_insight.news
hält sie als JSON-Text (Liste pro Wert mit Satz und Quellen), leer an ruhigen Tagen
und bei älteren Einträgen. Nur eine neue Spalte, an bestehenden Daten ändert sich nichts.

Revision ID: 0013_insight_news
Revises: 0012_price_alerts
Create Date: 2026-11-14 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0013_insight_news'
down_revision = '0012_price_alerts'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('daily_insight', sa.Column('news', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('daily_insight') as batch_op:
        batch_op.drop_column('news')
