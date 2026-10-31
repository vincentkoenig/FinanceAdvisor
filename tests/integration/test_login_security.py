"""
test_login_security.py - Tests für die Anmeldung: Session-Cookie, Logout,
gesperrte Registrierung, Verifizierungscodes mit begrenzten Versuchen,
Begrenzung der Anfragen, Schutz gegen Anfragen fremder Seiten und die
CLI-Befehle zur Kontoverwaltung.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.auth.routes import LOGIN_FAILED_MESSAGE, MAX_VERIFICATION_ATTEMPTS
from fintrack.config import Config
from fintrack.extensions import db, limiter
from fintrack.models import User
from tests.conftest import TEST_PASSWORD


class TestSession:

    def test_login_sets_secure_session_cookie(self, app, make_user):
        """Nach dem Login gibt es ein HttpOnly-Cookie mit SameSite=Lax,
        und /me kennt den Nutzer"""
        make_user('a@test.com')
        client = app.test_client()

        response = client.post('/api/v1/auth/login', json={'email': 'a@test.com', 'password': TEST_PASSWORD})

        cookies = ' '.join(response.headers.getlist('Set-Cookie'))
        assert 'HttpOnly' in cookies and 'SameSite=Lax' in cookies
        assert client.get('/api/v1/me').get_json()['email'] == 'a@test.com'

    def test_email_is_case_insensitive(self, app, make_user, login_client):
        make_user('a@test.com')

        client = login_client('  A@Test.COM ')

        assert client.get('/api/v1/me').status_code == 200

    def test_logout_ends_session(self, make_user, login_client):
        make_user('a@test.com')
        client = login_client('a@test.com')

        client.post('/api/v1/auth/logout')

        assert client.get('/api/v1/me').status_code == 401

    def test_start_page_leads_to_frontend_with_or_without_login(self, app, make_user, login_client):
        """Ob jemand angemeldet ist, prüft das Frontend selbst über /api/v1/me"""
        make_user('a@test.com')

        assert app.test_client().get('/').headers['Location'].endswith('/app/')
        assert login_client('a@test.com').get('/home-page').headers['Location'].endswith('/app/')

    def test_unknown_email_and_wrong_password_look_identical(self, app, make_user):
        """Man kann nicht herausfinden, welche E-Mails registriert sind"""
        make_user('a@test.com')
        client = app.test_client()

        wrong_password = client.post('/api/v1/auth/login', json={'email': 'a@test.com', 'password': 'falsch-falsch'})
        unknown_email = client.post('/api/v1/auth/login', json={'email': 'gibtsnicht@test.com', 'password': 'falsch-falsch'})

        assert wrong_password.status_code == unknown_email.status_code == 401
        assert wrong_password.get_json() == unknown_email.get_json() == {"error": LOGIN_FAILED_MESSAGE}

    def test_password_change_logs_out_all_devices(self, app, make_user, login_client):
        """set-password erneuert das session_token - alte Cookies sind ungültig"""
        make_user('a@test.com')
        client = login_client('a@test.com')

        result = app.test_cli_runner().invoke(
            args=['set-password', 'a@test.com', '--password', 'ganz-neues-passwort'])

        assert result.exit_code == 0, result.output
        assert client.get('/api/v1/me').status_code == 401
        assert login_client('a@test.com', 'ganz-neues-passwort').get('/api/v1/me').status_code == 200


class TestRegistration:

    def test_registration_closed_by_config(self, app, monkeypatch):
        monkeypatch.setitem(app.config, 'ALLOW_REGISTRATION', False)

        response = app.test_client().post('/api/v1/auth/register', json={
            'email': 'neu@test.com', 'password': 'langes-passwort'})

        assert response.status_code == 403
        assert User.query.count() == 0

    def test_registration_requires_minimum_password_length(self, app):
        response = app.test_client().post('/api/v1/auth/register', json={
            'email': 'neu@test.com', 'password': 'kurz'})

        assert response.status_code == 400
        assert 'mindestens' in response.get_json()['error']


def register(client, email='neu@test.com'):
    client.post('/api/v1/auth/register', json={'email': email, 'password': 'langes-passwort'})
    return User.query.filter_by(email=email).one()


class TestVerification:

    def test_correct_code_verifies_and_logs_in(self, app):
        client = app.test_client()
        user = register(client)

        response = client.post('/api/v1/auth/verify-email', json={'email': 'neu@test.com', 'code': user.verification_code})

        assert response.status_code == 200
        assert client.get('/api/v1/me').get_json()['email'] == 'neu@test.com'

    def test_code_locked_after_too_many_wrong_attempts(self, app):
        """Nach MAX_VERIFICATION_ATTEMPTS falschen Codes hilft auch der
        richtige nicht mehr - ein neuer Code muss her"""
        client = app.test_client()
        user = register(client)
        correct_code = user.verification_code
        wrong_code = '000000' if correct_code != '000000' else '111111'

        for _ in range(MAX_VERIFICATION_ATTEMPTS):
            client.post('/api/v1/auth/verify-email', json={'email': 'neu@test.com', 'code': wrong_code})
        response = client.post('/api/v1/auth/verify-email', json={'email': 'neu@test.com', 'code': correct_code})

        assert response.status_code == 429
        assert db.session.get(User, user.id).is_verified is False

    def test_resend_gives_fresh_attempts(self, app):
        client = app.test_client()
        user = register(client)
        for _ in range(MAX_VERIFICATION_ATTEMPTS):
            client.post('/api/v1/auth/verify-email', json={'email': 'neu@test.com', 'code': 'falsch'})

        client.post('/api/v1/auth/resend-verification', json={'email': 'neu@test.com'})
        db.session.refresh(user)
        response = client.post('/api/v1/auth/verify-email', json={'email': 'neu@test.com', 'code': user.verification_code})

        assert response.status_code == 200

    def test_resend_does_not_reveal_unknown_emails(self, app):
        client = app.test_client()
        register(client)

        known = client.post('/api/v1/auth/resend-verification', json={'email': 'neu@test.com'})
        unknown = client.post('/api/v1/auth/resend-verification', json={'email': 'gibtsnicht@test.com'})

        assert known.status_code == unknown.status_code == 200
        assert known.get_json() == unknown.get_json()


class TestRequestProtection:

    def test_login_rate_limited(self):
        """Nach 10 Login-Versuchen pro Minute kommt 429 als JSON. Eigene App,
        weil die Begrenzung in der normalen Testkonfiguration aus ist."""
        from fintrack import create_app
        limited_app = create_app('testing', {'RATELIMIT_ENABLED': True})
        try:
            with limited_app.app_context():
                db.create_all()
                client = limited_app.test_client()
                statuses = [client.post('/api/v1/auth/login', json={'email': 'a@test.com', 'password': 'falsch-falsch'}).status_code
                            for _ in range(11)]
                db.session.remove()
                db.drop_all()
        finally:
            # Limiter ist ein gemeinsames Objekt - für die übrigen Tests wieder aus
            limiter.enabled = False

        assert statuses[:10] == [401] * 10
        assert statuses[10] == 429

    def test_cross_site_requests_rejected(self, make_user, login_client):
        """Ändernde Anfragen mit Origin einer fremden Seite werden abgewiesen"""
        make_user('a@test.com')
        client = login_client('a@test.com')

        evil = client.post('/api/v1/me/categories/init-defaults',
                           headers={'Origin': 'https://boese-seite.example'})
        same_site = client.post('/api/v1/me/categories/init-defaults',
                                headers={'Origin': 'http://localhost'})

        assert evil.status_code == 403
        assert same_site.status_code == 201


class TestConfigSafety:

    def test_production_requires_secret_key(self, monkeypatch):
        """Ohne SECRET_KEY startet die App in Produktion nicht"""
        monkeypatch.setenv('RENDER', 'true')
        monkeypatch.delenv('SECRET_KEY', raising=False)

        with pytest.raises(RuntimeError, match='SECRET_KEY'):
            Config()

    def test_production_uses_secure_cookies(self, monkeypatch):
        monkeypatch.setenv('RENDER', 'true')
        monkeypatch.setenv('SECRET_KEY', 'x' * 64)

        config = Config()

        assert config.SESSION_COOKIE_SECURE is True
        assert config.REMEMBER_COOKIE_SECURE is True
        assert config.ALLOW_REGISTRATION is False


class TestCli:

    def test_create_user(self, app, login_client):
        result = app.test_cli_runner().invoke(
            args=['create-user', 'Neu@Test.com', '--password', 'langes-passwort'])

        assert result.exit_code == 0, result.output
        user = User.query.filter_by(email='neu@test.com').one()
        assert user.is_verified is True
        assert login_client('neu@test.com', 'langes-passwort').get('/api/v1/me').status_code == 200

    def test_create_user_rejects_short_password(self, app):
        result = app.test_cli_runner().invoke(args=['create-user', 'neu@test.com', '--password', 'kurz'])

        assert result.exit_code != 0
        assert User.query.count() == 0
