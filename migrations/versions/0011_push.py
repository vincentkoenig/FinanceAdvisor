"""push notifications

Push-Benachrichtigungen aufs Handy: push_subscription speichert pro Gerät, wohin
der Server Meldungen schickt und welche Arten es bekommt; push_log merkt sich, was
schon verschickt wurde. Zwei neue Tabellen, an bestehenden Daten ändert sich nichts.

Revision ID: 0011_push
Revises: 0010_suggestion_dismissal
Create Date: 2026-11-12 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0011_push'
down_revision = '0010_suggestion_dismissal'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'push_subscription',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('endpoint', sa.String(length=1000), nullable=False),
        sa.Column('p256dh', sa.String(length=200), nullable=False),
        sa.Column('auth', sa.String(length=100), nullable=False),
        sa.Column('deadlines', sa.Boolean(), nullable=False),
        sa.Column('savings_plan', sa.Boolean(), nullable=False),
        sa.Column('daily_update', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('endpoint'),
    )
    op.create_table(
        'push_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'key'),
    )


def downgrade():
    op.drop_table('push_log')
    op.drop_table('push_subscription')
