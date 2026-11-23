"""savings goals

Sparziele als Töpfe vom Kontostand: savings_goal (Ziel mit Betrag, optional Datum und
monatlicher Rate) und savings_goal_entry (Einzahlungen und Entnahmen). Nur neue Tabellen,
an bestehenden Daten ändert sich nichts.

Revision ID: 0019_savings_goals
Revises: 0018_bank_sync
Create Date: 2026-11-23 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0019_savings_goals'
down_revision = '0018_bank_sync'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'savings_goal',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('target_amount', sa.Float(), nullable=False),
        sa.Column('target_date', sa.Date(), nullable=True),
        sa.Column('monthly_amount', sa.Float(), nullable=True),
        sa.Column('rate_since', sa.Date(), nullable=True),
        sa.Column('reached_at', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'savings_goal_entry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('goal_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('kind', sa.String(length=10), nullable=False),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['goal_id'], ['savings_goal.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('savings_goal_entry')
    op.drop_table('savings_goal')
