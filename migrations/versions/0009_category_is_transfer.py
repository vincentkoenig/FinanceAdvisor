"""category is_transfer

Umbuchungen zwischen eigenen Konten: Solche Buchungen bewegen Geld und zählen für den
Kontostand, aber nicht als Einnahme oder Ausgabe. Die Richtung kommt weiter aus type,
darum gibt es je Nutzer eine Kategorie "Umbuchungen" für Eingänge und eine für Abgänge.
Bestehende Kategorien und Buchungen bleiben unverändert.

Revision ID: 0009_category_is_transfer
Revises: 0008_account_balance
Create Date: 2026-11-07 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0009_category_is_transfer'
down_revision = '0008_account_balance'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('category', sa.Column('is_transfer', sa.Boolean(), nullable=False, server_default=sa.false()))

    connection = op.get_bind()
    for category_type in ('income', 'variable_expense'):
        connection.execute(sa.text(
            "INSERT INTO category (user_id, name, type, is_transfer) "
            "SELECT id, 'Umbuchungen', :type, :yes FROM \"user\" "
            "WHERE id IN (SELECT user_id FROM category)"
        ), {"type": category_type, "yes": True})


def downgrade():
    connection = op.get_bind()
    # Buchungen in Umbuchungen fielen sonst auf eine fehlende Kategorie zurück
    used = connection.execute(sa.text(
        'SELECT COUNT(*) FROM "transaction" t JOIN category c ON t.category_id = c.id WHERE c.is_transfer = :yes'
    ), {"yes": True}).scalar()
    if used:
        raise RuntimeError('Es gibt Buchungen in Umbuchungs-Kategorien, erst umbuchen')
    connection.execute(sa.text(
        "DELETE FROM category_rule WHERE category_id IN (SELECT id FROM category WHERE is_transfer = :yes)"), {"yes": True})
    connection.execute(sa.text(
        "DELETE FROM category WHERE is_transfer = :yes AND parent_id IS NOT NULL"), {"yes": True})
    connection.execute(sa.text("DELETE FROM category WHERE is_transfer = :yes"), {"yes": True})
    with op.batch_alter_table('category') as batch:
        batch.drop_column('is_transfer')
