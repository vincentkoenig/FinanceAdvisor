"""
test_access_control.py - Stellt sicher, dass
- ohne Anmeldung keine Daten erreichbar sind (für JEDE Route der App),
- ein angemeldeter Nutzer nie an die Daten eines anderen Nutzers kommt:
  weder beim Lesen seiner /me-Routen noch über Objekt-IDs (Buchungen,
  Kategorien, Sparpläne, Positionen, Watchlist) noch über eine user_id im
  Request-Body.

Die Routen werden direkt aus der App gelesen: Kommt später eine neue
Route dazu, wird sie automatisch mitgeprüft.
"""

import sys
import os
import re
from datetime import date, datetime
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.extensions import db
from fintrack.models import (Asset, Category, ChatHistory, Contract, SavingsPlan, Transaction,
                             UserAsset, Watchlist)
from tests.conftest import flask_app

# Routen, die bewusst ohne Anmeldung erreichbar sind
PUBLIC_ENDPOINTS = {
    'auth.register', 'auth.login', 'auth.logout',
    'auth.verify_email', 'auth.resend_verification',
    # Das React-Frontend unter /app: reine Dateien ohne Nutzerdaten,
    # die Anmeldung prüft es selbst über /api/v1/me
    'spa.app_root', 'spa.frontend',
    # Weiterleitungen von / und den früheren Seiten nach /app
    'spa.legacy_root', 'spa.legacy_home_page', 'spa.legacy_portfolio_page', 'spa.legacy_budget_page',
    'spa.legacy_chat_page', 'spa.legacy_analyse_page', 'spa.legacy_settings_page',
    # Statuspunkt für Docker und Überwachung, ohne Nutzerdaten
    'health.healthz',
}

# Texte, die nur in den Daten von Nutzer B vorkommen - tauchen sie in einer
# Antwort an Nutzer A auf, sind fremde Daten durchgerutscht
FOREIGN_MARKERS = [b'geheime Frage von B', b'B-Haupt', b'B-Unter', b'B-Buchung', b'Testaktie von B', b'B-Vertrag']


def all_routes():
    """Alle Routen der App als (Endpoint, URL-Muster, Methode)."""
    routes = []
    for rule in flask_app.url_map.iter_rules():
        for method in sorted(rule.methods - {'HEAD', 'OPTIONS'}):
            routes.append((rule.endpoint, rule.rule, method))
    return routes


def fill(rule, **values):
    """Setzt Werte in ein URL-Muster ein, z.B. /x/<int:plan_id> -> /x/7."""
    return re.sub(r'<(?:\w+:)?(\w+)>', lambda m: str(values.get(m.group(1), 1)), rule)


PROTECTED_ROUTES = [r for r in all_routes()
                    if r[0] not in PUBLIC_ENDPOINTS and not r[0].startswith('admin.')]
# Lesende /me-Routen ohne Platzhalter - die "Liste meiner Daten"-Routen
ME_READ_ROUTES = [r for r in PROTECTED_ROUTES
                  if r[1].startswith('/api/v1/me') and r[2] == 'GET' and '<' not in r[1]]


class TestAnonymousAccess:
    """Ohne Anmeldung"""

    @pytest.mark.parametrize('endpoint,rule,method', PROTECTED_ROUTES,
                             ids=[f'{m} {r}' for _, r, m in PROTECTED_ROUTES])
    def test_every_protected_route_requires_login(self, app, endpoint, rule, method):
        """Jede nicht-öffentliche Route antwortet ohne Anmeldung mit 401"""
        client = app.test_client()

        response = client.open(fill(rule), method=method, json={})

        assert response.status_code == 401

    def test_start_page_leads_to_the_frontend(self, app):
        response = app.test_client().get('/')
        assert response.status_code == 302
        assert response.headers['Location'].endswith('/app/')

    def test_no_user_ids_in_api_urls(self):
        """Die API nimmt nie eine User-ID aus der URL - wer gemeint ist,
        entscheidet allein die Anmeldung"""
        assert not [r for _, r, _ in all_routes() if 'user_id' in r]


@pytest.fixture
def two_users(make_user, login_client):
    """
    Nutzer A ist angemeldet und hat keine Daten, Nutzer B besitzt Daten aller Art.
    Gibt (client_a, user_a, user_b, b_data) zurück.
    """
    user_a = make_user('a@test.com')
    user_b = make_user('b@test.com')

    asset = Asset(name='Testaktie von B', symbol='TEST', asset_type='unknown', currency='EUR')
    db.session.add(asset)
    db.session.flush()

    b_parent = Category(user_id=user_b.id, name='B-Haupt', type='variable_expense')
    db.session.add(b_parent)
    db.session.flush()
    b_category = Category(user_id=user_b.id, name='B-Unter', type='variable_expense', parent_id=b_parent.id)
    db.session.add(b_category)
    db.session.flush()

    b_transaction = Transaction(user_id=user_b.id, category_id=b_category.id, amount=50,
                                description='B-Buchung', date=datetime(2026, 10, 1), is_recurring=True)
    b_plan = SavingsPlan(user_id=user_b.id, asset_id=asset.id, amount=100, day_of_month=1)
    b_contract = Contract(user_id=user_b.id, name='B-Vertrag', category='insurance', amount=10,
                          interval='monthly', start_date=date(2026, 1, 1), renewal_months=12,
                          notice_value=3, notice_unit='months')
    db.session.add_all([
        b_transaction, b_plan, b_contract,
        UserAsset(user_id=user_b.id, asset_id=asset.id, quantity=3, avg_buy_price=10, status='owned'),
        Watchlist(user_id=user_b.id, asset_id=asset.id, price_added=10),
        ChatHistory(user_id=user_b.id, role='user', message='geheime Frage von B'),
    ])
    db.session.commit()

    b_data = SimpleNamespace(asset=asset, parent=b_parent, category=b_category,
                             transaction=b_transaction, plan=b_plan, contract=b_contract)
    return login_client('a@test.com'), user_a, user_b, b_data


class TestForeignUserData:
    """Angemeldet als A, Daten gehören B"""

    @pytest.mark.parametrize('endpoint,rule,method', ME_READ_ROUTES,
                             ids=[f'{m} {r}' for _, r, m in ME_READ_ROUTES])
    def test_my_routes_never_return_foreign_data(self, two_users, endpoint, rule, method):
        """Keine lesende /me-Route liefert Daten von B aus"""
        client, _, _, _ = two_users

        response = client.get(rule)

        assert response.status_code == 200
        for marker in FOREIGN_MARKERS:
            assert marker not in response.data, f'{rule} liefert fremde Daten: {marker!r}'

    @pytest.mark.parametrize('method,url_template', [
        ('DELETE', '/api/v1/me/transactions/{transaction}'),
        ('POST', '/api/v1/me/transactions/{transaction}/toggle-pause'),
        ('DELETE', '/api/v1/me/categories/{category}'),
        ('DELETE', '/api/v1/me/savings-plans/{plan}'),
        ('POST', '/api/v1/me/savings-plans/{plan}/execute'),
        ('DELETE', '/api/v1/me/watchlist/{asset}'),
        ('PUT', '/api/v1/me/contracts/{contract}'),
        ('DELETE', '/api/v1/me/contracts/{contract}'),
        ('POST', '/api/v1/me/contracts/{contract}/cancel'),
        ('DELETE', '/api/v1/me/contracts/{contract}/cancel'),
        ('DELETE', '/api/v1/me/contracts/{contract}/booking'),
    ])
    def test_foreign_objects_cannot_be_changed(self, two_users, method, url_template):
        """Objekte von B lassen sich über ihre ID weder ändern noch löschen"""
        client, _, user_b, b_data = two_users
        url = url_template.format(transaction=b_data.transaction.id, category=b_data.category.id,
                                  plan=b_data.plan.id, asset=b_data.asset.id, contract=b_data.contract.id)
        # Gültiger Vertrags-Body, damit die Prüfung nicht schon an der Eingabe scheitert
        body = {'name': 'von A', 'category': 'other', 'amount': 1, 'interval': 'monthly',
                'start_date': '2026-01-01'} if 'contracts' in url else None

        response = client.open(url, method=method, json=body)

        assert response.status_code == 404
        db.session.expire_all()
        assert db.session.get(Transaction, b_data.transaction.id).is_paused is False
        assert db.session.get(Category, b_data.category.id) is not None
        assert db.session.get(SavingsPlan, b_data.plan.id).last_executed is None
        assert Watchlist.query.filter_by(user_id=user_b.id).count() == 1
        b_contract = db.session.get(Contract, b_data.contract.id)
        assert b_contract.name == 'B-Vertrag' and b_contract.end_date is None

    def test_cannot_sell_foreign_position(self, two_users):
        """A kann die Position von B nicht verkaufen - für A existiert sie nicht"""
        client, _, user_b, b_data = two_users

        response = client.post(f'/api/v1/me/positions/{b_data.asset.id}/sell', json={'quantity': 1})

        assert response.status_code == 404
        db.session.expire_all()
        assert UserAsset.query.filter_by(user_id=user_b.id).one().quantity == 3

    def test_cannot_book_into_foreign_category(self, two_users):
        """Eine Buchung in einer Kategorie von B wird abgelehnt"""
        client, user_a, _, b_data = two_users

        response = client.post('/api/v1/me/transactions', json={
            'category_id': b_data.category.id, 'amount': 10, 'date': '2026-10-01'})

        assert response.status_code == 404
        assert Transaction.query.filter_by(user_id=user_a.id).count() == 0

    @pytest.mark.parametrize('target', ['category', 'transaction'])
    def test_contract_cannot_use_foreign_booking_or_category(self, two_users, target):
        """Ein Vertrag von A lässt sich weder mit einer Buchung noch einer Kategorie von B verknüpfen"""
        client, user_a, _, b_data = two_users
        own = client.post('/api/v1/me/contracts', json={
            'name': 'von A', 'category': 'other', 'amount': 1, 'interval': 'monthly', 'start_date': '2026-01-01'})
        contract_id = own.get_json()['contract']['id']
        body = {'category_id': b_data.category.id} if target == 'category' else {'transaction_id': b_data.transaction.id}

        response = client.post(f'/api/v1/me/contracts/{contract_id}/booking', json=body)

        assert response.status_code == 404
        assert db.session.get(Contract, contract_id).transaction_id is None
        assert Transaction.query.filter_by(user_id=user_a.id).count() == 0

    def test_cannot_create_subcategory_under_foreign_category(self, two_users):
        client, _, _, b_data = two_users

        response = client.post('/api/v1/me/categories', json={
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

        response = client.post('/api/v1/me/chat', json={'user_id': user_b.id, 'message': 'Hallo'})

        assert response.status_code == 200
        assert ChatHistory.query.filter_by(user_id=user_a.id, message='Hallo').count() == 1
        assert ChatHistory.query.filter_by(user_id=user_b.id, message='Hallo').count() == 0


class TestAdminOnlyRoutes:
    def test_manual_price_entry_needs_admin_key(self, two_users, monkeypatch):
        """Die Preistabelle gilt für alle Nutzer - ein normaler Login reicht nicht"""
        client, _, _, b_data = two_users
        monkeypatch.setenv('ADMIN_API_KEY', 'geheim')

        response = client.post(f'/api/v1/admin/assets/{b_data.asset.id}/prices',
                               json={'date': '2026-10-01', 'price': 1, 'currency': 'EUR'})

        assert response.status_code == 403
