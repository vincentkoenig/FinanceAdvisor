"""
conftest.py - Gemeinsame pytest-Fixtures für alle Tests.
Stellt eine isolierte, In-Memory-Testdatenbank bereit, damit Tests
niemals gegen die echte lokale Datenbank laufen.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Zusätzliches Sicherheitsnetz: Auch Code, der die Konfiguration selbst
# über get_config() wählt, landet so in der Testkonfiguration.
os.environ['TESTING'] = '1'

import pytest

from fintrack import create_app
from fintrack.models import db, User, Category, Transaction

# Die App wird direkt über die Factory gebaut (nicht über app.py), damit
# in den Tests kein Scheduler mit Hintergrundjobs startet.
flask_app = create_app('testing')


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


@pytest.fixture(autouse=True)
def no_real_emails(mocker):
    """Verhindert in allen Tests den echten Versand über Resend."""
    return mocker.patch('fintrack.auth.routes.send_verification_email', return_value=True)


TEST_PASSWORD = 'sicheres-test-passwort'


@pytest.fixture
def make_user(app):
    """
    Legt einen bestätigten Nutzer mit echtem Passwort-Hash an.
    Aufruf: make_user('a@test.com') -> User
    """
    from werkzeug.security import generate_password_hash

    def _make_user(email, password=TEST_PASSWORD):
        # Schnelles Hash-Verfahren nur für Tests - die App selbst nutzt den
        # sicheren (absichtlich langsamen) Standard von werkzeug
        user = User(username=email.split('@')[0], email=email,
                    password=generate_password_hash(password, method='pbkdf2:sha256:1000'),
                    is_verified=True)
        db.session.add(user)
        db.session.commit()
        return user

    return _make_user


@pytest.fixture
def login_client(app):
    """
    Liefert einen Test-Client, der als der angegebene Nutzer angemeldet ist.
    Aufruf: login_client('a@test.com') -> FlaskClient
    """
    def _login_client(email, password=TEST_PASSWORD):
        client = app.test_client()
        response = client.post('/login', json={'email': email, 'password': password})
        assert response.status_code == 200, response.get_json()
        return client

    return _login_client


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