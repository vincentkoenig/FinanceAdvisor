"""
test_access_control.py - Stellt sicher, dass
- ohne Anmeldung keine Daten erreichbar sind (für JEDE Route der App),
- ein angemeldeter Nutzer nie an die Daten eines anderen Nutzers kommt,
  weder über die user_id in der URL noch über Objekt-IDs (Buchungen,
  Kategorien, Sparpläne) noch über eine user_id im Request-Body.

Die Routen werden direkt aus der App gelesen: Kommt später eine neue
Route dazu, wird sie automatisch mitgeprüft.
"""

import sys
import os
import re
from datetime import datetime
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from tests.conftest import flask_app
from fintrack.extensions import db
from fintrack.models import (Asset, Category, ChatHistory, SavingsPlan, Transaction,
                             UserAsset, Watchlist)

# Routen, die bewusst ohne Anmeldung erreichbar sind
PUBLIC_ENDPOINTS = {
    'static', 'pages.home',
    'auth.register', 'auth.login', 'auth.logout', 'auth.me',
    'auth.verify_email', 'auth.resend_verification',
}


def all_routes():
    """Alle Routen der App als (Endpoint, URL-Muster, Methode)."""
    routes = []
    for rule in flask_app.url_map.iter_rules():
        for method in sorted(rule.methods - {'HEAD', 'OPTIONS'}):
            routes.append((rule.endpoint, rule.rule, method))
    return routes


def fill(rule, **values):
    """Setzt Werte in ein URL-Muster ein, z.B. /users/<user_id>/x -> /users/7/x."""
    return re.sub(r'<(?:\w+:)?(\w+)>', lambda m: str(values.get(m.group(1), 1)), rule)


PROTECTED_ROUTES = [r for r in all_routes()
                    if r[0] not in PUBLIC_ENDPOINTS and not r[0].startswith('admin.')]
USER_ID_ROUTES = [r for r in PROTECTED_ROUTES if '<user_id>' in r[1]]


class TestAnonymousAccess:
    """Ohne Anmeldung"""

    @pytest.mark.parametrize('endpoint,rule,method', PROTECTED_ROUTES,
                             ids=[f'{m} {r}' for _, r, m in PROTECTED_ROUTES])
    def test_every_protected_route_requires_login(self, app, endpoint, rule, method):
        """Jede nicht-öffentliche Route verweigert den Zugriff: Seiten leiten
        zum Login um, API-Routen antworten mit 401"""
        client = app.test_client()

        response = client.open(fill(rule), method=method, json={})

        if endpoint.startswith('pages.'):
            assert response.status_code == 302
            assert response.headers['Location'].endswith('/')
        else:
            assert response.status_code == 401

    def test_login_page_is_public(self, app):
        assert app.test_client().get('/').status_code == 200


@pytest.fixture
def two_users(make_user, login_client):
    """
    Nutzer A ist angemeldet, Nutzer B besitzt Daten aller Art.
    Gibt (client_a, user_a, user_b, b_data) zurück.
    """
    user_a = make_user('a@test.com')
    user_b = make_user('b@test.com')

    asset = Asset(name='Testaktie', symbol='TEST', asset_type='unknown', currency='EUR')
    db.session.add(asset)
    db.session.flush()

    b_parent = Category(user_id=user_b.id, name='B-Haupt', type='variable_expense')
    db.session.add(b_parent)
    db.session.flush()
    b_category = Category(user_id=user_b.id, name='B-Unter', type='variable_expense', parent_id=b_parent.id)
    db.session.add(b_category)
    db.session.flush()

    b_transaction = Transaction(user_id=user_b.id, category_id=b_category.id, amount=50,
                                date=datetime(2026, 10, 1), is_recurring=True)
    b_plan = SavingsPlan(user_id=user_b.id, asset_id=asset.id, amount=100, day_of_month=1)
    db.session.add_all([
        b_transaction, b_plan,
        UserAsset(user_id=user_b.id, asset_id=asset.id, quantity=3, avg_buy_price=10, status='owned'),
        Watchlist(user_id=user_b.id, asset_id=asset.id, price_added=10),
        ChatHistory(user_id=user_b.id, role='user', message='geheime Frage von B'),
    ])
    db.session.commit()

    b_data = SimpleNamespace(asset=asset, parent=b_parent, category=b_category,
                             transaction=b_transaction, plan=b_plan)
    return login_client('a@test.com'), user_a, user_b, b_data


class TestForeignUserData:
    """Angemeldet als A, Zugriff auf Daten von B"""

    @pytest.mark.parametrize('endpoint,rule,method', USER_ID_ROUTES,
                             ids=[f'{m} {r}' for _, r, m in USER_ID_ROUTES])
    def test_foreign_user_id_in_url_is_not_found(self, two_users, endpoint, rule, method):
        """Jede Route mit user_id in der URL liefert für fremde IDs 404"""
        client, _, user_b, b_data = two_users

        response = client.open(fill(rule, user_id=user_b.id, asset_id=b_data.asset.id),
                               method=method, json={})

        assert response.status_code == 404

    def test_own_user_id_in_url_works(self, two_users):
        """Gegenprobe: die eigenen Daten sind erreichbar"""
        client, user_a, _, _ = two_users

        assert client.get(f'/users/{user_a.id}/categories').status_code == 200

    def test_foreign_chat_history_not_readable(self, two_users):
        client, _, user_b, _ = two_users

        response = client.get(f'/chat/history/{user_b.id}')

        assert response.status_code == 404
        assert b'geheime Frage' not in response.data

    @pytest.mark.parametrize('method,url_template', [
        ('DELETE', '/transactions/{transaction}'),
        ('PUT', '/transactions/{transaction}/toggle-pause'),
        ('DELETE', '/categories/{category}'),
        ('DELETE', '/savings-plans/{plan}'),
        ('POST', '/savings-plans/{plan}/execute'),
    ])
    def test_foreign_objects_cannot_be_changed(self, two_users, method, url_template):
        """Objekte von B lassen sich über ihre ID weder ändern noch löschen"""
        client, _, user_b, b_data = two_users
        url = url_template.format(transaction=b_data.transaction.id,
                                  category=b_data.category.id, plan=b_data.plan.id)

        response = client.open(url, method=method)

        assert response.status_code == 404
        db.session.expire_all()
        assert db.session.get(Transaction, b_data.transaction.id).is_paused is False
        assert db.session.get(Category, b_data.category.id) is not None
        assert db.session.get(SavingsPlan, b_data.plan.id) is not None

    def test_cannot_book_into_foreign_category(self, two_users):
        """Eine Buchung in einer Kategorie von B wird abgelehnt"""
        client, user_a, _, b_data = two_users

        response = client.post(f'/users/{user_a.id}/transactions', json={
            'category_id': b_data.category.id, 'amount': 10, 'date': '2026-10-01'})

        assert response.status_code == 404
        assert Transaction.query.filter_by(user_id=user_a.id).count() == 0

    def test_cannot_create_subcategory_under_foreign_category(self, two_users):
        client, user_a, _, b_data = two_users

        response = client.post(f'/users/{user_a.id}/categories', json={
            'name': 'Untergeschoben', 'type': 'variable_expense', 'parent_id': b_data.parent.id})

        assert response.status_code == 404
        assert Category.query.filter_by(name='Untergeschoben').count() == 0

    def test_chat_ignores_user_id_in_body(self, two_users, mocker):
        """Eine fremde user_id im Body wird ignoriert - die Nachricht landet
        immer beim angemeldeten Nutzer"""
        client, user_a, user_b, _ = two_users
        fake_message = SimpleNamespace(tool_calls=None, content='Antwort des Assistenten')
        fake_client = mocker.MagicMock()
        fake_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=fake_message)])
        mocker.patch('fintrack.chat.routes.get_openai_client', return_value=fake_client)

        response = client.post('/chat', json={'user_id': user_b.id, 'message': 'Hallo'})

        assert response.status_code == 200
        assert ChatHistory.query.filter_by(user_id=user_a.id, message='Hallo').count() == 1
        assert ChatHistory.query.filter_by(user_id=user_b.id, message='Hallo').count() == 0


class TestAdminOnlyRoutes:
    def test_manual_price_entry_needs_admin_key(self, two_users, monkeypatch):
        """Die Preistabelle gilt für alle Nutzer - ein normaler Login reicht nicht"""
        client, _, _, b_data = two_users
        monkeypatch.setenv('ADMIN_API_KEY', 'geheim')

        response = client.post(f'/assets/{b_data.asset.id}/prices',
                               json={'date': '2026-10-01', 'price': 1, 'currency': 'EUR'})

        assert response.status_code == 403
