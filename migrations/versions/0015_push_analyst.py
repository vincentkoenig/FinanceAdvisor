"""push analyst

Push-Meldung, wenn sich eine Einschätzung des Analysten gegenüber der Vorwoche
ändert: push_subscription bekommt den Schalter analyst. Schon angemeldete Geräte
bekommen ihn eingeschaltet, wie neue Geräte auch. Nur eine neue Spalte.

Revision ID: 0015_push_analyst
Revises: 0014_analyst
Create Date: 2026-11-14 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0015_push_analyst'
down_revision = '0014_analyst'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('push_subscription', sa.Column('analyst', sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade():
    with op.batch_alter_table('push_subscription') as batch_op:
        batch_op.drop_column('analyst')
