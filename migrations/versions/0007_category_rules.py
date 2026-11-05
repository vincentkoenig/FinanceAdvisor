"""category rules

Feste Zuordnungen für den Kontoimport: Steht pattern (als ganzes Wort) im Empfänger
oder Verwendungszweck eines Umsatzes in derselben Richtung (income), schlägt die
Vorschau category_id vor. Gelöscht wird eine Regel mit ihrer Kategorie.

Revision ID: 0007_category_rules
Revises: 0006_import_hash
Create Date: 2026-11-05 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0007_category_rules'
down_revision = '0006_import_hash'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'category_rule',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('pattern', sa.String(length=100), nullable=False),
        sa.Column('income', sa.Boolean(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.ForeignKeyConstraint(['category_id'], ['category.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'pattern', 'income'),
    )


def downgrade():
    op.drop_table('category_rule')
