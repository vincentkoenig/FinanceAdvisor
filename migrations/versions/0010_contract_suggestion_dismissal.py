"""contract suggestion dismissal

Ausgeblendete Vertragsvorschläge standen bisher nur im Browser (localStorage) und
tauchten auf einem anderen Gerät wieder auf. Jetzt merkt sie sich der Server, je
Nutzer ein Eintrag pro kleingeschriebenem Empfängernamen. Neue Tabelle, an
bestehenden Daten ändert sich nichts.

Revision ID: 0010_contract_suggestion_dismissal
Revises: 0009_category_is_transfer
Create Date: 2026-11-08 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0010_contract_suggestion_dismissal'
down_revision = '0009_category_is_transfer'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'contract_suggestion_dismissal',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'key'),
    )


def downgrade():
    op.drop_table('contract_suggestion_dismissal')
