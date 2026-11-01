"""contract booking

Verträge können mit ihrer wiederkehrenden Buchung im Haushaltsbuch verknüpft
werden (contract.transaction_id). Wird die Buchung gelöscht, bleibt der
Vertrag und verliert nur die Verknüpfung. Bestehende Verträge bleiben
unverknüpft.

Revision ID: 0005_contract_booking
Revises: 0004_contracts
Create Date: 2026-11-01 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0005_contract_booking'
down_revision = '0004_contracts'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('contract', schema=None) as batch_op:
        batch_op.add_column(sa.Column('transaction_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('contract_transaction_id_fkey'), 'transaction', ['transaction_id'], ['id'],
                                    ondelete='SET NULL')


def downgrade():
    with op.batch_alter_table('contract', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('contract_transaction_id_fkey'), type_='foreignkey')
        batch_op.drop_column('transaction_id')
