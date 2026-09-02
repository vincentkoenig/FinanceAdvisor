"""
conftest.py - Gemeinsame pytest-Fixtures für alle Tests.
Stellt eine isolierte, In-Memory-Testdatenbank bereit, damit Tests
niemals gegen die echte lokale Datenbank laufen.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# WICHTIG: Muss VOR dem Import von app.py gesetzt werden, damit app.py
# beim Initialisieren die In-Memory-Testdatenbank statt der echten
# lokalen Datenbank nutzt.
os.environ['TESTING'] = '1'

import pytest

from app import app as flask_app
from models import db, User, Category, Transaction


@pytest.fixture
def app():
    """
    Stellt die echte Flask-App (mit allen registrierten Routen) bereit,
    die dank TESTING=1 bereits beim Import an eine In-Memory-Datenbank
    gebunden wurde.
    """
    with flask_app.app_context():
        # Sicherheitsnetz: Testlauf sofort abbrechen, falls die
        # tatsächlich genutzte DB-URI aus irgendeinem Grund NICHT auf
        # die In-Memory-Datenbank zeigt.
        actual_uri = str(db.engine.url)
        assert 'memory' in actual_uri, (
            f"SICHERHEITSABBRUCH: Tests würden gegen '{actual_uri}' laufen, "
            f"nicht gegen die In-Memory-Testdatenbank!"
        )

        db.create_all()
        yield flask_app
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