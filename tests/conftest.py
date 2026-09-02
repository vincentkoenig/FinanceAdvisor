"""
conftest.py - Gemeinsame pytest-Fixtures für alle Tests.
Stellt eine isolierte, In-Memory-Testdatenbank bereit, damit Tests
niemals gegen die echte lokale Datenbank laufen.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from flask import Flask

from models import db, User, Category, Transaction


@pytest.fixture
def app():
    """
    Erstellt eine komplett eigene, separate Flask-App-Instanz nur für
    Tests, mit einer In-Memory-SQLite-Datenbank. Nutzt bewusst NICHT
    die App-Instanz aus app.py, da diese beim Import bereits fest an
    die echte Datei-Datenbank gebunden wird und sich nachträglich
    nicht zuverlässig umkonfigurieren lässt.
    """
    test_app = Flask(__name__)
    test_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    test_app.config['TESTING'] = True

    db.init_app(test_app)

    with test_app.app_context():
        # Sicherheitsnetz: Testlauf sofort abbrechen, falls die
        # tatsächlich genutzte DB-URI aus irgendeinem Grund NICHT auf
        # die In-Memory-Datenbank zeigt.
        actual_uri = str(db.engine.url)
        assert 'memory' in actual_uri, (
            f"SICHERHEITSABBRUCH: Tests würden gegen '{actual_uri}' laufen, "
            f"nicht gegen die In-Memory-Testdatenbank!"
        )

        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def test_user(app):
    """Legt einen einfachen Test-Nutzer an."""
    user = User(username="testuser", email="test@test.com", password="hashed")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def income_category(app, test_user):
    """Legt eine einfache Einkommens-Kategorie für den Test-Nutzer an."""
    category = Category(user_id=test_user.id, name="Gehalt", type="income")
    db.session.add(category)
    db.session.commit()
    return category


@pytest.fixture
def expense_category(app, test_user):
    """Legt eine einfache Ausgaben-Kategorie für den Test-Nutzer an."""
    category = Category(user_id=test_user.id, name="Miete", type="fixed_expense")
    db.session.add(category)
    db.session.commit()
    return category