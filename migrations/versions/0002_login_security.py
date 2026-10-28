"""login security: verification attempts and session token

verification_attempts begrenzt die Fehlversuche pro Verifizierungscode,
session_token erlaubt es, alle Anmeldungen eines Nutzers ungültig zu machen.
Bestehende Nutzer bekommen 0 Versuche und noch kein Token (wird beim
nächsten Login erzeugt).

Revision ID: 0002_login_security
Revises: 0001_baseline
Create Date: 2026-10-28 22:20:34.347523

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002_login_security'
down_revision = '0001_baseline'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('verification_attempts', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('session_token', sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('session_token')
        batch_op.drop_column('verification_attempts')
