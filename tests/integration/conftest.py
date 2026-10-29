"""
conftest.py (integration) - Gemeinsame Fixture für Migrationstests:
eine eigene App mit leerer, echter Datenbank. Läuft gegen SQLite und
zusätzlich gegen PostgreSQL, wenn TEST_POSTGRES_URL gesetzt ist (in der CI).
"""

import os

import pytest
from sqlalchemy import MetaData

from fintrack import create_app
from fintrack.config import normalize_database_url
from fintrack.extensions import db


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
