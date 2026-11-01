"""import hash

Kontoumsätze lassen sich aus CSV-Dateien importieren. Jede so angelegte Buchung
bekommt einen Fingerabdruck (transaction.import_hash), eindeutig je Nutzer,
damit derselbe Umsatz bei einem zweiten Import nicht doppelt gebucht wird.
Bestehende Buchungen bekommen keinen (NULL zählt nicht als doppelt).

Revision ID: 0006_import_hash
Revises: 0005_contract_booking
Create Date: 2026-11-01 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0006_import_hash'
down_revision = '0005_contract_booking'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.add_column(sa.Column('import_hash', sa.String(length=40), nullable=True))
        batch_op.create_unique_constraint(batch_op.f('transaction_user_id_key'), ['user_id', 'import_hash'])


def downgrade():
    with op.batch_alter_table('transaction', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('transaction_user_id_key'), type_='unique')
        batch_op.drop_column('import_hash')
