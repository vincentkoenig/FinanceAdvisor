"""bank sync

Bankabruf über Enable Banking (PSD2): bank_connection (Zugang zu einer Bank),
bank_account (Konten daraus) und bank_transaction (jeder abgerufene Umsatz genau
einmal, mit dem, was daraus wurde). Nur neue Tabellen, an bestehenden Daten
ändert sich nichts.

Revision ID: 0018_bank_sync
Revises: 0017_tax_joint
Create Date: 2026-11-22 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0018_bank_sync'
down_revision = '0017_tax_joint'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'bank_connection',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('aspsp_name', sa.String(length=200), nullable=False),
        sa.Column('aspsp_country', sa.String(length=2), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('state', sa.String(length=64), nullable=True),
        sa.Column('session_id', sa.String(length=200), nullable=True),
        sa.Column('valid_until', sa.DateTime(), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('state'),
    )
    op.create_table(
        'bank_account',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('connection_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.String(length=200), nullable=False),
        sa.Column('identification_hash', sa.String(length=200), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('iban_last4', sa.String(length=4), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('synced_until', sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(['connection_id'], ['bank_connection.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'bank_transaction',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('ext_key', sa.String(length=64), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('counterparty', sa.String(length=500), nullable=False),
        sa.Column('purpose', sa.String(length=1000), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('category_source', sa.String(length=20), nullable=True),
        sa.Column('transaction_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['category_id'], ['category.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transaction.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'ext_key'),
    )


def downgrade():
    op.drop_table('bank_transaction')
    op.drop_table('bank_account')
    op.drop_table('bank_connection')
