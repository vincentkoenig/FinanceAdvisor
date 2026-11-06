"""account balance

Vom Nutzer eingetragene echte Kontostände, von denen aus der Cash-Bestand weitergerechnet
wird. Nur eine neue Tabelle, bestehende Daten bleiben unberührt.

Revision ID: 0008_account_balance
Revises: 0007_category_rules
Create Date: 2026-11-06 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0008_account_balance'
down_revision = '0007_category_rules'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'account_balance',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'date'),
    )


def downgrade():
    op.drop_table('account_balance')
