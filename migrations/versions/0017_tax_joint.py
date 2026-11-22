"""tax joint

Sparerpauschbetrag für Verheiratete: user bekommt den Schalter tax_joint
(gemeinsame Veranlagung, 2.000 € statt 1.000 €). Bestehende Nutzer starten mit
"nein", wie neue auch. Nur eine neue Spalte.

Revision ID: 0017_tax_joint
Revises: 0016_passkeys
Create Date: 2026-11-22 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0017_tax_joint'
down_revision = '0016_passkeys'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('tax_joint', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('user') as batch_op:
        batch_op.drop_column('tax_joint')
