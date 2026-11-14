"""passkeys

Anmeldung per Face ID, Touch ID oder Fingerabdruck (WebAuthn): passkey speichert pro
Gerät den öffentlichen Schlüssel. Neue Tabelle, an bestehenden Daten ändert sich nichts.

Revision ID: 0016_passkeys
Revises: 0015_push_analyst
Create Date: 2026-11-14 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0016_passkeys'
down_revision = '0015_push_analyst'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'passkey',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('credential_id', sa.String(length=512), nullable=False),
        sa.Column('public_key', sa.LargeBinary(), nullable=False),
        sa.Column('sign_count', sa.Integer(), nullable=False),
        sa.Column('transports', sa.String(length=200), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('credential_id'),
    )
    op.create_index('ix_passkey_user_id', 'passkey', ['user_id'])


def downgrade():
    op.drop_index('ix_passkey_user_id', table_name='passkey')
    op.drop_table('passkey')
