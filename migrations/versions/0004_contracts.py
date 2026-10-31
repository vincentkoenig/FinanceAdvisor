"""contracts

Neue Tabelle contract für Verträge (Versicherungen, Strom, Handy, Abos, ...)
mit Laufzeit, Kündigungsfrist und optionaler Kündigung. Bestehende Tabellen
bleiben unverändert.

Revision ID: 0004_contracts
Revises: 0003_price_data_model
Create Date: 2026-11-01 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004_contracts'
down_revision = '0003_price_data_model'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('contract',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('provider', sa.String(), nullable=True),
    sa.Column('category', sa.String(), nullable=False),
    sa.Column('contract_number', sa.String(), nullable=True),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.Column('interval', sa.String(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('min_term_months', sa.Integer(), nullable=True),
    sa.Column('renewal_months', sa.Integer(), nullable=True),
    sa.Column('notice_value', sa.Integer(), nullable=False),
    sa.Column('notice_unit', sa.String(), nullable=False),
    sa.Column('cancelled_at', sa.Date(), nullable=True),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('notes', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('contract_user_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('contract_pkey'))
    )


def downgrade():
    op.drop_table('contract')
