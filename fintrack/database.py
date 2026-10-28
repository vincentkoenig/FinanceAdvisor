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
        # wenn sie exakt dem Schema der Modelle entspricht. Das ist nur für
        # die Umstellung auf Alembic gedacht, solange die Modelle noch der
        # Basis-Migration entsprechen - danach legt create_all() keine
        # Datenbanken mehr an, und der Fall tritt nicht mehr auf.
        differences = schema_differences()
        if differences:
            raise SchemaMismatchError(
                'Die bestehende Datenbank weicht vom erwarteten Schema ab, '
                f'es wurde nichts verändert. {describe_differences(differences)}')
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
