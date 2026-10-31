"""
test_health.py - Statuspunkt /healthz: ohne Anmeldung erreichbar, ohne
Datenbankzugriff im Normalfall, mit Datenbankprüfung nur auf Wunsch.
"""

from unittest.mock import patch

from sqlalchemy.exc import OperationalError

from fintrack.extensions import db


def test_healthz_answers_without_login(app):
    response = app.test_client().get('/healthz')

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_healthz_does_not_touch_the_database(app):
    """Sonst hält ein Docker-Healthcheck Neon dauerhaft wach"""
    with patch.object(db.session, 'execute') as execute:
        app.test_client().get('/healthz')

    execute.assert_not_called()


def test_healthz_checks_the_database_on_request(app):
    response = app.test_client().get('/healthz?db=1')

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "database": "ok"}


def test_healthz_reports_an_unreachable_database_without_details(app):
    error = OperationalError('SELECT 1', {}, Exception('password authentication failed for user x'))
    with patch.object(db.session, 'execute', side_effect=error):
        response = app.test_client().get('/healthz?db=1')

    assert response.status_code == 503
    assert response.get_json() == {"status": "error", "database": "nicht erreichbar"}
    assert b'password' not in response.data
