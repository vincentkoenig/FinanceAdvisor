"""
test_migrations.py - Tests für die Datenbank-Migrationen (Alembic) und
den Befehl "flask upgrade-db". Stellt sicher, dass
- die Migrationen exakt das Schema der Modelle erzeugen,
- bestehende Datenbanken aus der Zeit vor Alembic samt Daten übernommen werden,
- eine abweichende Datenbank nicht angefasst wird.

Laufen immer gegen eine SQLite-Datei und zusätzlich gegen PostgreSQL, wenn
TEST_POSTGRES_URL gesetzt ist (in der CI über einen Postgres-Container).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from sqlalchemy import inspect, text

from flask_migrate import upgrade

from fintrack.database import BASELINE_REVISION, SchemaMismatchError, schema_differences, upgrade_database
from fintrack.extensions import db
from fintrack.models import User

def current_revision():
    with db.engine.connect() as connection:
        return connection.execute(text('SELECT version_num FROM alembic_version')).scalar()


def head_revision():
    """Neueste Migration laut migrations/versions"""
    from alembic.script import ScriptDirectory
    from flask import current_app
    config = current_app.extensions['migrate'].migrate.get_config()
    return ScriptDirectory.from_config(config).get_current_head()


def create_pre_alembic_database():
    """
    Baut eine Datenbank wie aus der Zeit vor Alembic nach: Schema der
    Basis-Migration, aber ohne Versionstabelle (so hat create_all() sie
    damals angelegt).
    """
    upgrade(revision=BASELINE_REVISION)
    with db.engine.begin() as connection:
        connection.execute(text('DROP TABLE alembic_version'))


class TestUpgradeDatabase:
    """Tests für upgrade_database() bzw. "flask upgrade-db" """

    def test_creates_new_database_matching_models(self, migration_app):
        """Eine leere Datenbank wird per Migration angelegt und entspricht
        danach exakt den Modellen"""
        assert upgrade_database() == 'created'

        assert schema_differences() == []
        assert current_revision() == head_revision()

    def test_second_run_changes_nothing(self, migration_app):
        """Ein zweiter Lauf erkennt den aktuellen Stand und ändert nichts"""
        upgrade_database()

        assert upgrade_database() == 'upgraded'
        assert schema_differences() == []

    def test_adopts_existing_database_and_keeps_data(self, migration_app):
        """Eine früher über create_all() angelegte Datenbank wird übernommen,
        ohne Tabellen neu anzulegen, und danach auf den neuesten Stand
        migriert - vorhandene Daten bleiben erhalten"""
        create_pre_alembic_database()
        with db.engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO \"user\" (username, email, password) VALUES ('bestand', 'bestand@test.com', 'x')"))

        assert upgrade_database() == 'adopted'

        assert current_revision() == head_revision()
        bestand = User.query.filter_by(email='bestand@test.com').one()
        # Spalte aus Migration 0002: bestehende Nutzer starten mit 0 Fehlversuchen
        assert bestand.verification_attempts == 0
        assert schema_differences() == []

    def test_rejects_database_with_different_schema(self, migration_app):
        """Weicht eine bestehende Datenbank vom Schema ab, bricht der Befehl ab
        und verändert nichts - es wird auch nichts als migriert markiert"""
        with db.engine.begin() as connection:
            connection.execute(text('CREATE TABLE "user" (id INTEGER PRIMARY KEY, username VARCHAR NOT NULL)'))

        with pytest.raises(SchemaMismatchError, match='Spalte fehlt: user.email'):
            upgrade_database()

        assert set(inspect(db.engine).get_table_names()) == {'user'}


class TestUpgradeCommand:
    """Test für den CLI-Befehl selbst"""

    def test_cli_command_reports_result(self, migration_app):
        """"flask upgrade-db" läuft durch und meldet, was passiert ist"""
        runner = migration_app.test_cli_runner()

        result = runner.invoke(args=['upgrade-db'])

        assert result.exit_code == 0, result.output
        assert 'Neue Datenbank angelegt' in result.output
