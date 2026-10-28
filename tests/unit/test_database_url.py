"""
test_database_url.py - Unit Tests für normalize_database_url().
Stellt sicher, dass jede Postgres-Schreibweise der Anbieter (Render,
Neon) auf den installierten Treiber psycopg2 zeigt - unabhängig davon,
welchen Treiber SQLAlchemy standardmäßig wählen würde.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from sqlalchemy.engine import make_url

from app import normalize_database_url


NEON_REST = 'nutzer:geheim@ep-abc-123.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'


class TestNormalizeDatabaseUrl:
    """Unit Tests für die Umwandlung der DATABASE_URL"""

    @pytest.mark.parametrize('scheme', ['postgres', 'postgresql', 'postgresql+psycopg', 'postgresql+psycopg2'])
    def test_postgres_urls_use_psycopg2(self, scheme):
        """Alle üblichen Postgres-Schreibweisen werden auf psycopg2 umgestellt"""
        result = normalize_database_url(f'{scheme}://{NEON_REST}')

        assert result == f'postgresql+psycopg2://{NEON_REST}'

    def test_sqlalchemy_resolves_psycopg2_driver(self):
        """SQLAlchemy erkennt in der umgewandelten URL den Treiber psycopg2,
        Host und Parameter wie sslmode bleiben erhalten"""
        url = make_url(normalize_database_url(f'postgresql://{NEON_REST}'))

        assert url.get_dialect().driver == 'psycopg2'
        assert url.host == 'ep-abc-123.eu-central-1.aws.neon.tech'
        assert url.query['sslmode'] == 'require'

    def test_sqlite_url_unchanged(self):
        """Nicht-Postgres-URLs wie SQLite bleiben unverändert"""
        assert normalize_database_url('sqlite:///finance_advisor.db') == 'sqlite:///finance_advisor.db'
