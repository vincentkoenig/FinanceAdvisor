"""
conftest.py - Gemeinsame pytest-Fixtures für alle Tests.
Stellt eine isolierte, In-Memory-Testdatenbank bereit, damit Tests
nicht gegen die echte lokale Datenbank laufen.
"""

import sys
import os
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app as flask_app
from models import db, User, Category, Transaction


@pytest.fixture
def app():
    """
    Stellt die Flask-App mit einer In-Memory-SQLite-Datenbank bereit,
    statt der echten Datei-Datenbank. Jeder Test bekommt eine frische,
    leere Datenbank.
    """
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    flask_app.config['TESTING'] = True

    with flask_app.app_context():
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