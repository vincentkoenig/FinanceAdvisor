"""
database.py - Datenbank auf den neuesten Stand bringen.
Führt die Alembic-Migrationen aus und prüft danach, dass die Tabellen
in der Datenbank exakt zu den Modellen passen.

Sonderfall bestehende Datenbanken: Die Produktionsdatenbank und lokale
SQLite-Dateien wurden früher über db.create_all() angelegt und haben
deshalb noch keine Alembic-Versionstabelle. Solche Datenbanken werden
einmalig als "auf Stand der Basis-Migration" markiert (stamp), statt
die Tabellen noch einmal anzulegen. Weicht das Schema ab, bricht der
Befehl ab, bevor irgendetwas verändert wird.
"""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import stamp, upgrade
from sqlalchemy import inspect

from fintrack.extensions import db

# Revision der ersten Migration, die das Schema zum Zeitpunkt der
# Einführung von Alembic abbildet (migrations/versions/0001_baseline.py)
BASELINE_REVISION = '0001_baseline'

# Fester Abdruck der Tabellen und Spalten aus 0001_baseline. Damit wird eine
# Datenbank aus der Zeit vor Alembic geprüft, bevor sie übernommen wird -
# unabhängig davon, wie sich die Modelle seitdem weiterentwickelt haben.
# Darf nicht geändert werden, solange es die Basis-Migration gibt.
BASELINE_SCHEMA = {
    'asset': {'id', 'name', 'symbol', 'asset_type', 'currency'},
    'asset_transaction': {'id', 'user_id', 'asset_id', 'type', 'quantity', 'price', 'date'},
    'category': {'id', 'user_id', 'name', 'type', 'parent_id'},
    'chat_history': {'id', 'user_id', 'message', 'role', 'created_at'},
    'daily_insight': {'id', 'user_id', 'content', 'created_at'},
    'dividend': {'id', 'user_id', 'asset_id', 'ex_dividend_date', 'amount_per_share', 'shares_held',
                 'total_amount', 'transaction_id', 'booked_at'},
    'portfolio_analysis': {'id', 'user_id', 'total_value', 'risk_assessment', 'diversification_score',
                           'summary', 'recommendations', 'allocation', 'created_at'},
    'price_history': {'id', 'asset_id', 'date', 'price', 'currency'},
    'savings_plan': {'id', 'user_id', 'asset_id', 'amount', 'day_of_month', 'start_date',
                     'last_executed', 'active'},
    'transaction': {'id', 'user_id', 'category_id', 'amount', 'description', 'date', 'is_recurring',
                    'end_date', 'is_paused', 'paused_at'},
    'user': {'id', 'username', 'email', 'password', 'age', 'gender', 'risk_profile',
             'investment_experience', 'monthly_budget', 'investment_horizon', 'created_at',
             'is_verified', 'verification_code', 'verification_code_expires'},
    'user_asset': {'id', 'user_id', 'asset_id', 'quantity', 'avg_buy_price', 'bought_at', 'status'},
    'watchlist': {'id', 'user_id', 'asset_id', 'added_at', 'price_added'},
}


class SchemaMismatchError(RuntimeError):
    """Die Tabellen in der Datenbank passen nicht zu den Modellen."""


def describe_differences(differences):
    """
    Fasst die Unterschiede aus compare_metadata() kurz und lesbar
    zusammen, z.B. "Tabelle fehlt: asset" oder "Spalte fehlt: user.email".
    """
    labels = {
        'add_table': 'Tabelle fehlt',
        'remove_table': 'Tabelle zu viel',
        'add_column': 'Spalte fehlt',
        'remove_column': 'Spalte zu viel',
        'modify_type': 'Typ weicht ab',
        'modify_nullable': 'NULL-Regel weicht ab',
    }
    lines = []
    # Spaltenänderungen liefert Alembic als Liste, alles andere als Tupel
    flat = [item for diff in differences for item in (diff if isinstance(diff, list) else [diff])]
    for diff in flat:
        kind = diff[0]
        label = labels.get(kind, kind)
        if kind in ('add_table', 'remove_table'):
            lines.append(f'{label}: {diff[1].name}')
        elif kind in ('add_column', 'remove_column'):
            lines.append(f'{label}: {diff[2]}.{diff[3].name}')
        elif kind.startswith('modify_'):
            lines.append(f'{label}: {diff[2]}.{diff[3]}')
        else:
            lines.append(label)
    return '; '.join(lines)


def baseline_differences():
    """
    Vergleicht Tabellen und Spalten der Datenbank mit dem Abdruck der
    Basis-Migration. Gibt eine lesbare Beschreibung der Unterschiede
    zurück (leer = passt). Typen prüft danach schema_differences(),
    sobald die Datenbank auf dem neuesten Stand ist.
    """
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names()) - {'alembic_version'}
    lines = [f'Tabelle fehlt: {t}' for t in sorted(set(BASELINE_SCHEMA) - tables)]
    lines += [f'Tabelle zu viel: {t}' for t in sorted(tables - set(BASELINE_SCHEMA))]
    for table in sorted(tables & set(BASELINE_SCHEMA)):
        columns = {c['name'] for c in inspector.get_columns(table)}
        lines += [f'Spalte fehlt: {table}.{c}' for c in sorted(BASELINE_SCHEMA[table] - columns)]
        lines += [f'Spalte zu viel: {table}.{c}' for c in sorted(columns - BASELINE_SCHEMA[table])]
    return '; '.join(lines)


def schema_differences():
    """
    Vergleicht die Tabellen in der Datenbank mit den SQLAlchemy-Modellen.
    Gibt eine Liste der Unterschiede zurück (leer = identisch). Die
    Alembic-Versionstabelle selbst wird dabei ignoriert.
    """
    with db.engine.connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={
                'compare_type': True,
                'include_name': lambda name, type_, parent: not (
                    type_ == 'table' and name == 'alembic_version'),
            },
        )
        return compare_metadata(context, db.metadata)


def upgrade_database():
    """
    Bringt die Datenbank auf den neuesten Stand und gibt zurück, was
    passiert ist ('created', 'adopted' oder 'upgraded').
    """
    existing_tables = set(inspect(db.engine).get_table_names())
    app_tables = set(db.metadata.tables)

    if 'alembic_version' not in existing_tables and existing_tables & app_tables:
        # Bestehende Datenbank aus der Zeit vor Alembic: nur übernehmen,
        # wenn Tabellen und Spalten exakt der Basis-Migration entsprechen.
        # Danach laufen die späteren Migrationen ganz normal darauf.
        differences = baseline_differences()
        if differences:
            raise SchemaMismatchError(
                'Die bestehende Datenbank weicht vom erwarteten Schema ab, '
                f'es wurde nichts verändert. {differences}')
        stamp(revision=BASELINE_REVISION)
        action = 'adopted'
    elif 'alembic_version' not in existing_tables:
        action = 'created'
    else:
        action = 'upgraded'

    upgrade()

    # Nach jeder Migration müssen Datenbank und Modelle übereinstimmen -
    # sonst fehlt eine Migration zu einer Modelländerung
    differences = schema_differences()
    if differences:
        raise SchemaMismatchError(
            'Datenbank und Modelle passen nach der Migration nicht zusammen - '
            f'fehlt eine Migration? {describe_differences(differences)}')

    return action
