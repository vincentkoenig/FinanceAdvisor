"""price data model

Grundlage für korrekte Kurse (Phase 2):
- Assets bekommen Börse und den Zeitpunkt der letzten Metadaten-Abfrage
- neue Tabelle fx_rate für Wechselkurse pro Tag
- Eindeutigkeit: ein Asset pro Symbol, ein Kurs pro Asset und Tag, eine
  Position und ein Watchlist-Eintrag pro Nutzer und Asset

Vorher werden bestehende Daten bereinigt, damit die Eindeutigkeit gelten kann:
1. Die Kurshistorie wird geleert. Sie mischt USD- und EUR-Werte und ist
   nicht zu reparieren; der Kurs-Job lädt sie in Originalwährung neu.
2. Doppelte Assets (gleiches Symbol) werden zum ältesten zusammengeführt,
   alle Verweise darauf werden umgehängt.
3. Doppelte Positionen eines Nutzers werden zu einer zusammengefasst
   (Mengen addiert, Durchschnittspreis mengengewichtet).
4. Doppelte Watchlist-Einträge eines Nutzers: der älteste bleibt.
5. Doppelt gebuchte Dividenden (Folge doppelter Assets) samt ihrer
   automatisch erzeugten Einnahme: eine bleibt.
Eingaben der Nutzer (Käufe, Verkäufe, Buchungen, Sparpläne) gehen dabei
nicht verloren - sie hängen danach nur am zusammengeführten Asset.

Revision ID: 0003_price_data_model
Revises: 0002_login_security
Create Date: 2026-10-29 12:57:51.676048

"""
from collections import defaultdict

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003_price_data_model'
down_revision = '0002_login_security'
branch_labels = None
depends_on = None

# Tabellen, die auf ein Asset verweisen (price_history wird ohnehin geleert)
ASSET_REFERENCES = ('user_asset', 'asset_transaction', 'savings_plan', 'watchlist', 'dividend')


def _merge_duplicate_assets(conn):
    """Assets mit gleichem Symbol zum ältesten (kleinste ID) zusammenführen."""
    ids_by_symbol = defaultdict(list)
    for asset_id, symbol in conn.execute(sa.text('SELECT id, symbol FROM asset ORDER BY id')):
        ids_by_symbol[symbol].append(asset_id)

    for ids in ids_by_symbol.values():
        keep, duplicates = ids[0], ids[1:]
        for duplicate in duplicates:
            for table in ASSET_REFERENCES:
                conn.execute(sa.text(f'UPDATE {table} SET asset_id = :keep WHERE asset_id = :duplicate'),
                             {'keep': keep, 'duplicate': duplicate})
            conn.execute(sa.text('DELETE FROM asset WHERE id = :duplicate'), {'duplicate': duplicate})


def _merge_duplicate_positions(conn):
    """Mehrere Positionen eines Nutzers für dasselbe Asset zu einer zusammenfassen."""
    rows = conn.execute(sa.text(
        'SELECT id, user_id, asset_id, quantity, avg_buy_price, bought_at FROM user_asset ORDER BY id'
    )).fetchall()
    groups = defaultdict(list)
    for row in rows:
        groups[(row.user_id, row.asset_id)].append(row)

    for positions in groups.values():
        if len(positions) < 2:
            continue
        keep = positions[0]
        quantity = sum(p.quantity or 0 for p in positions)
        cost = sum((p.quantity or 0) * (p.avg_buy_price or 0) for p in positions)
        # Ohne Bestand gibt es keinen sinnvollen Mittelwert - dann den
        # Kaufpreis der ersten Position behalten
        avg_price = round(cost / quantity, 2) if quantity > 0 else keep.avg_buy_price
        bought_at = min((p.bought_at for p in positions if p.bought_at is not None), default=None)

        conn.execute(sa.text(
            'UPDATE user_asset SET quantity = :quantity, avg_buy_price = :avg_price, '
            'bought_at = :bought_at, status = :status WHERE id = :id'
        ), {'quantity': quantity, 'avg_price': avg_price, 'bought_at': bought_at,
            'status': 'owned' if quantity > 0 else 'sold', 'id': keep.id})
        for duplicate in positions[1:]:
            conn.execute(sa.text('DELETE FROM user_asset WHERE id = :id'), {'id': duplicate.id})


def _merge_duplicate_watchlist(conn):
    """Doppelte Watchlist-Einträge entfernen, der älteste bleibt."""
    rows = conn.execute(sa.text('SELECT id, user_id, asset_id FROM watchlist ORDER BY id')).fetchall()
    seen = set()
    for row in rows:
        key = (row.user_id, row.asset_id)
        if key in seen:
            conn.execute(sa.text('DELETE FROM watchlist WHERE id = :id'), {'id': row.id})
        seen.add(key)


def _merge_duplicate_dividends(conn):
    """
    Gab es ein Asset doppelt, hat der Dividenden-Job dieselbe Ausschüttung
    für beide gebucht - inklusive einer automatisch erzeugten Einnahme im
    Haushaltsbuch. Nach dem Zusammenführen bleibt je Nutzer, Asset und
    Ex-Tag eine Dividende; die doppelt erzeugten Einnahmen werden entfernt.
    Von Hand angelegte Buchungen sind nie betroffen.
    """
    rows = conn.execute(sa.text(
        'SELECT id, user_id, asset_id, ex_dividend_date, transaction_id FROM dividend ORDER BY id'
    )).fetchall()
    seen = set()
    for row in rows:
        key = (row.user_id, row.asset_id, row.ex_dividend_date)
        if key in seen:
            conn.execute(sa.text('DELETE FROM dividend WHERE id = :id'), {'id': row.id})
            if row.transaction_id is not None:
                conn.execute(sa.text('DELETE FROM "transaction" WHERE id = :id'), {'id': row.transaction_id})
        seen.add(key)


def upgrade():
    conn = op.get_bind()

    # ─── Bereinigung (siehe Kopf der Datei) ───
    conn.execute(sa.text('DELETE FROM price_history'))
    _merge_duplicate_assets(conn)
    _merge_duplicate_positions(conn)
    _merge_duplicate_watchlist(conn)
    _merge_duplicate_dividends(conn)

    # ─── Schema ───
    op.create_table('fx_rate',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('rate_to_eur', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('fx_rate_pkey')),
    sa.UniqueConstraint('currency', 'date', name=op.f('fx_rate_currency_key'))
    )
    with op.batch_alter_table('asset', schema=None) as batch_op:
        batch_op.add_column(sa.Column('exchange', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('metadata_updated_at', sa.DateTime(), nullable=True))
        batch_op.create_unique_constraint(batch_op.f('asset_symbol_key'), ['symbol'])

    with op.batch_alter_table('price_history', schema=None) as batch_op:
        batch_op.create_unique_constraint(batch_op.f('price_history_asset_id_key'), ['asset_id', 'date'])

    with op.batch_alter_table('user_asset', schema=None) as batch_op:
        batch_op.create_unique_constraint(batch_op.f('user_asset_user_id_key'), ['user_id', 'asset_id'])

    with op.batch_alter_table('watchlist', schema=None) as batch_op:
        batch_op.create_unique_constraint(batch_op.f('watchlist_user_id_key'), ['user_id', 'asset_id'])


def downgrade():
    # Nimmt nur das Schema zurück. Zusammengeführte Assets und Positionen
    # sowie die geleerte Kurshistorie lassen sich nicht wiederherstellen -
    # dafür gibt es das Backup vor der Migration.
    with op.batch_alter_table('watchlist', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('watchlist_user_id_key'), type_='unique')

    with op.batch_alter_table('user_asset', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('user_asset_user_id_key'), type_='unique')

    with op.batch_alter_table('price_history', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('price_history_asset_id_key'), type_='unique')

    with op.batch_alter_table('asset', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('asset_symbol_key'), type_='unique')
        batch_op.drop_column('metadata_updated_at')
        batch_op.drop_column('exchange')

    op.drop_table('fx_rate')
