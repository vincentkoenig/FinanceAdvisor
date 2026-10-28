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
from sqlalchemy import MetaData, inspect, text

from fintrack import create_app
from fintrack.config import normalize_database_url
from fintrack.database import BASELINE_REVISION, SchemaMismatchError, schema_differences, upgrade_database
from fintrack.extensions import db
from fintrack.models import User

BACKENDS = ['sqlite']
if os.getenv('TEST_POSTGRES_URL'):
    BACKENDS.append('postgres')


def drop_everything():
    """Entfernt alle Tabellen inkl. alembic_version - für eine saubere Ausgangslage."""
    metadata = MetaData()
    metadata.reflect(bind=db.engine)
    metadata.drop_all(bind=db.engine)


@pytest.fixture(params=BACKENDS)
def migration_app(request, tmp_path):
    """
    Eigene App mit einer leeren, echten Datenbank (keine In-Memory-DB),
    damit Migrationen wie in Produktion laufen.
    """
    if request.param == 'sqlite':
        url = f'sqlite:///{tmp_path / "migration_test.db"}'
    else:
        url = normalize_database_url(os.environ['TEST_POSTGRES_URL'])

    app = create_app('testing', {'SQLALCHEMY_DATABASE_URI': url})
    with app.app_context():
        drop_everything()
        yield app
        db.session.remove()
        drop_everything()
        db.engine.dispose()


def current_revision():
    with db.engine.connect() as connection:
        return connection.execute(text('SELECT version_num FROM alembic_version')).scalar()


class TestUpgradeDatabase:
    """Tests für upgrade_database() bzw. "flask upgrade-db" """

    def test_creates_new_database_matching_models(self, migration_app):
        """Eine leere Datenbank wird per Migration angelegt und entspricht
        danach exakt den Modellen"""
        assert upgrade_database() == 'created'

        assert schema_differences() == []
        assert current_revision() == BASELINE_REVISION

    def test_second_run_changes_nothing(self, migration_app):
        """Ein zweiter Lauf erkennt den aktuellen Stand und ändert nichts"""
        upgrade_database()

        assert upgrade_database() == 'upgraded'
        assert schema_differences() == []

    def test_adopts_existing_database_and_keeps_data(self, migration_app):
        """Eine früher über create_all() angelegte Datenbank wird übernommen,
        ohne Tabellen neu anzulegen - vorhandene Daten bleiben erhalten"""
        db.create_all()
        db.session.add(User(username='bestand', email='bestand@test.com', password='x'))
        db.session.commit()

        assert upgrade_database() == 'adopted'

        assert current_revision() == BASELINE_REVISION
        assert User.query.filter_by(email='bestand@test.com').count() == 1
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
