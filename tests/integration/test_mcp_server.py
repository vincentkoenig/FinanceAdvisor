"""
test_mcp_server.py - Tests für den MCP-Server (mcp_server/server.py).
Er nutzt dieselbe App wie die Web-App und greift auf das Konto aus
FINTRACK_USER_EMAIL zu - nicht mehr auf eine fest eingebaute User-ID.
"""

import sys
import os
import importlib.util
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from werkzeug.security import generate_password_hash

from fintrack.budget.service import create_default_categories
from fintrack.extensions import db
from fintrack.models import Category, Transaction, User

SERVER_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                           'mcp_server', 'server.py')


@pytest.fixture
def server():
    """
    Lädt den MCP-Server frisch. Dank TESTING=1 (siehe conftest) baut er
    seine App mit einer eigenen In-Memory-Datenbank.
    """
    spec = importlib.util.spec_from_file_location('fintrack_mcp_server', SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with module.app.app_context():
        db.create_all()
        yield module
        db.session.remove()
        db.drop_all()


def make_account(email):
    user = User(username=email.split('@')[0], email=email,
                password=generate_password_hash('x' * 12, method='pbkdf2:sha256:1000'), is_verified=True)
    db.session.add(user)
    db.session.commit()
    create_default_categories(user.id)
    return user


def test_uses_test_database(server):
    assert 'memory' in str(db.engine.url)


def test_explains_missing_configuration(server, monkeypatch):
    monkeypatch.delenv('FINTRACK_USER_EMAIL', raising=False)

    assert 'FINTRACK_USER_EMAIL ist nicht gesetzt' in server.get_budget_status()


def test_unknown_email(server, monkeypatch):
    monkeypatch.setenv('FINTRACK_USER_EMAIL', 'gibtsnicht@test.com')

    assert 'Kein FinTrack-Konto' in server.get_portfolio_summary()


def test_works_on_configured_account_only(server, monkeypatch):
    """Buchungen landen beim Konto aus FINTRACK_USER_EMAIL, nicht bei Nutzer 1"""
    first = make_account('erster@test.com')
    mine = make_account('ich@test.com')
    monkeypatch.setenv('FINTRACK_USER_EMAIL', 'Ich@Test.com')

    result = server.add_transaction('lebensmittel', 42.5, 'Wocheneinkauf', '2026-10-20')

    assert 'Ausgabe erfolgreich eingetragen' in result
    assert Transaction.query.filter_by(user_id=mine.id).count() == 1
    assert Transaction.query.filter_by(user_id=first.id).count() == 0


def test_budget_status_uses_shared_logic(server, monkeypatch):
    user = make_account('ich@test.com')
    gehalt = Category.query.filter_by(user_id=user.id, name='Gehalt').one()
    db.session.add(Transaction(user_id=user.id, category_id=gehalt.id, amount=3000,
                               date=datetime.now().replace(day=1)))
    db.session.commit()
    monkeypatch.setenv('FINTRACK_USER_EMAIL', 'ich@test.com')

    assert 'Einnahmen: 3000.0 €' in server.get_budget_status()


def test_main_category_rejected(server, monkeypatch):
    make_account('ich@test.com')
    monkeypatch.setenv('FINTRACK_USER_EMAIL', 'ich@test.com')

    assert 'Hauptkategorie' in server.add_transaction('Lebenshaltung', 10)
