"""
test_auth_routes.py - Integration Tests für die Auth-Endpoints
(/register, /login, /verify-email). Testet den kompletten
Request-Response-Zyklus über den Flask Test-Client.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from models import User, db


class TestRegisterRoute:
    """Integration Tests für POST /register"""

    def test_register_creates_user(self, app):
        """Eine Registrierung mit gültigen Daten legt einen neuen Nutzer an
        und liefert Status 201 zurück"""
        client = app.test_client()

        response = client.post('/register', json={
            'email': 'neu@test.com',
            'password': 'sicheres_passwort'
        })

        assert response.status_code == 201
        data = response.get_json()
        assert 'user_id' in data

    def test_register_creates_default_categories(self, app):
        """Nach der Registrierung hat der neue Nutzer automatisch
        Standard-Budgetkategorien"""
        from models import Category

        client = app.test_client()
        response = client.post('/register', json={
            'email': 'kategorien@test.com',
            'password': 'passwort123'
        })

        user_id = response.get_json()['user_id']
        categories = Category.query.filter_by(user_id=user_id).all()

        assert len(categories) > 0

    def test_register_rejects_invalid_email(self, app):
        """Eine ungültige E-Mail-Adresse wird mit Status 400 abgelehnt"""
        client = app.test_client()

        response = client.post('/register', json={
            'email': 'keine-email',
            'password': 'passwort123'
        })

        assert response.status_code == 400

    def test_register_rejects_duplicate_email(self, app):
        """Eine bereits registrierte Email kann nicht erneut genutzt werden"""
        client = app.test_client()

        client.post('/register', json={
            'email': 'doppelt@test.com',
            'password': 'erstespasswort'
        })

        response = client.post('/register', json={
            'email': 'doppelt@test.com',
            'password': 'zweitespasswort'
        })

        assert response.status_code == 400


class TestLoginRoute:
    """Integration Tests für POST /login"""

    def test_login_blocked_for_unverified_account(self, app):
        """Ein frisch registrierter, noch nicht verifizierter Account
        kann sich nicht einloggen"""
        client = app.test_client()

        client.post('/register', json={
            'email': 'unverifiziert@test.com',
            'password': 'meinpasswort'
        })

        response = client.post('/login', json={
            'email': 'unverifiziert@test.com',
            'password': 'meinpasswort'
        })

        assert response.status_code == 403
        assert response.get_json()['needs_verification'] is True

    def test_login_succeeds_after_verification(self, app):
        """Nach manueller Verifizierung (is_verified=True) gelingt der
        Login mit korrekten Zugangsdaten"""
        client = app.test_client()

        client.post('/register', json={
            'email': 'verifiziert@test.com',
            'password': 'meinpasswort'
        })

        # Verifizierung direkt in der DB simulieren, statt den echten
        # Email-Versand zu testen (das übernehmen die Unit-Tests für
        # email_service.py)
        user = User.query.filter_by(email='verifiziert@test.com').first()
        user.is_verified = True
        db.session.commit()

        response = client.post('/login', json={
            'email': 'verifiziert@test.com',
            'password': 'meinpasswort'
        })

        assert response.status_code == 200
        assert 'user_id' in response.get_json()

    def test_login_with_wrong_password_fails(self, app):
        """Ein Login mit falschem Passwort schlägt fehl"""
        client = app.test_client()

        client.post('/register', json={
            'email': 'falsch@test.com',
            'password': 'richtiges_passwort'
        })

        response = client.post('/login', json={
            'email': 'falsch@test.com',
            'password': 'falsches_passwort'
        })

        assert response.status_code != 200