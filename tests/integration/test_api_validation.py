"""
test_api_validation.py - Tests für die Eingabeprüfung und die einheitlichen
Fehlerantworten der API unter /api/v1, sowie für fachliche Regeln, die
mit der neuen API dazugekommen sind.
"""

import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.extensions import db
from fintrack.models import Asset, AssetTransaction, Category, Transaction, UserAsset
from fintrack.portfolio.analysis import parse_stored_list


@pytest.fixture
def client(make_user, login_client):
    make_user('a@test.com')
    return login_client('a@test.com')


@pytest.fixture
def category(app, client):
    """Eigene Unterkategorie des angemeldeten Nutzers."""
    user_id = client.get('/api/v1/me').get_json()['id']
    parent = Category(user_id=user_id, name='Leben', type='variable_expense')
    db.session.add(parent)
    db.session.flush()
    sub = Category(user_id=user_id, name='Lebensmittel', type='variable_expense', parent_id=parent.id)
    db.session.add(sub)
    db.session.commit()
    return sub


@pytest.fixture
def asset(app):
    asset = Asset(name='Testaktie', symbol='TST', asset_type='unknown', currency='EUR')
    db.session.add(asset)
    db.session.commit()
    return asset


class TestValidationErrors:

    def test_missing_field_is_named(self, client, category):
        response = client.post('/api/v1/me/transactions', json={'category_id': category.id, 'date': '2026-10-01'})

        assert response.status_code == 400
        assert response.get_json()['fields'] == {'amount': 'Pflichtfeld fehlt'}

    @pytest.mark.parametrize('amount', [0, -5])
    def test_amount_must_be_positive(self, client, category, amount):
        response = client.post('/api/v1/me/transactions',
                               json={'category_id': category.id, 'amount': amount, 'date': '2026-10-01'})

        assert response.status_code == 400
        assert response.get_json()['fields']['amount'] == 'muss größer als 0 sein'

    def test_invalid_date(self, client, category):
        response = client.post('/api/v1/me/transactions',
                               json={'category_id': category.id, 'amount': 10, 'date': '31.10.2026'})

        assert response.status_code == 400
        assert 'JJJJ-MM-TT' in response.get_json()['fields']['date']

    def test_end_date_before_start(self, client, category):
        response = client.post('/api/v1/me/transactions', json={
            'category_id': category.id, 'amount': 10, 'date': '2026-10-01',
            'is_recurring': True, 'end_date': '2026-09-01'})

        assert response.status_code == 400
        assert 'Enddatum' in response.get_json()['error']

    def test_strings_with_numbers_are_accepted(self, client, category):
        """Das Frontend schickt Formularwerte als Text - "12.50" ist eine gültige Zahl"""
        response = client.post('/api/v1/me/transactions', json={
            'category_id': str(category.id), 'amount': '12.50', 'date': '2026-10-01', 'description': ''})

        assert response.status_code == 201
        transaction = Transaction.query.one()
        assert transaction.amount == 12.5
        assert transaction.description is None

    def test_invalid_month_filter(self, client):
        response = client.get('/api/v1/me/transactions?month=2026-13')

        assert response.status_code == 400
        assert 'month' in response.get_json()['fields']

    def test_body_must_be_json(self, client):
        response = client.post('/api/v1/me/transactions', data='kein json', content_type='text/plain')

        assert response.status_code == 400
        assert 'JSON' in response.get_json()['error']

    def test_savings_plan_day_limited_to_28(self, client, asset):
        response = client.post('/api/v1/me/savings-plans', json={'asset_id': asset.id, 'amount': 50, 'day_of_month': 31})

        assert response.status_code == 400
        assert response.get_json()['fields']['day_of_month'] == 'darf höchstens 28 sein'

    def test_purchase_date_not_in_future(self, client, asset):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        response = client.post('/api/v1/me/positions', json={
            'asset_id': asset.id, 'quantity': 1, 'avg_buy_price': 10, 'bought_at': tomorrow})

        assert response.status_code == 400
        assert 'Zukunft' in response.get_json()['fields']['bought_at']


class TestUniformErrors:

    def test_unknown_api_route_returns_json_404(self, client):
        response = client.get('/api/v1/gibt-es-nicht')

        assert response.status_code == 404
        assert response.get_json() == {'error': 'Nicht gefunden'}

    def test_wrong_method_returns_json_405(self, client):
        response = client.delete('/api/v1/me/budget/summary')

        assert response.status_code == 405
        assert 'error' in response.get_json()

    def test_unknown_asset_is_404(self, client):
        response = client.post('/api/v1/me/watchlist', json={'asset_id': 999})

        assert response.status_code == 404
        assert response.get_json() == {'error': 'Asset nicht gefunden'}


class TestPortfolioRules:

    def test_buying_owned_asset_extends_position(self, client, asset):
        """Ein zweiter Kauf über "Position hinzufügen" ergibt keine doppelte
        Position, sondern einen neuen Durchschnittspreis"""
        client.post('/api/v1/me/positions', json={'asset_id': asset.id, 'quantity': 2, 'avg_buy_price': 10, 'bought_at': '2026-10-01'})
        client.post('/api/v1/me/positions', json={'asset_id': asset.id, 'quantity': 2, 'avg_buy_price': 20, 'bought_at': '2026-10-02'})

        position = UserAsset.query.filter_by(asset_id=asset.id).one()
        assert position.quantity == 4
        assert position.avg_buy_price == 15
        assert AssetTransaction.query.count() == 2

    def test_positions_include_asset_type(self, client, asset):
        """Die Aufteilung im Portfolio gruppiert nach Anlageart"""
        client.post('/api/v1/me/positions', json={'asset_id': asset.id, 'quantity': 2, 'avg_buy_price': 10, 'bought_at': '2026-10-01'})

        positions = client.get('/api/v1/me/positions').get_json()

        assert [p['asset_type'] for p in positions] == ['unknown']

    def test_watchlist_includes_name_and_price(self, client, asset, monkeypatch):
        """Die Watchlist im neuen Frontend braucht keinen Request pro Zeile"""
        monkeypatch.setattr('fintrack.portfolio.routes.get_current_price', lambda a, **kw: 12.5)
        client.post('/api/v1/me/watchlist', json={'asset_id': asset.id})

        items = client.get('/api/v1/me/watchlist').get_json()

        assert items == [{'asset_id': asset.id, 'name': 'Testaktie', 'symbol': 'TST', 'price_added': 12.5,
                          'current_price': 12.5, 'added_at': items[0]['added_at']}]

    def test_sell_more_than_owned(self, client, asset):
        client.post('/api/v1/me/positions', json={'asset_id': asset.id, 'quantity': 2, 'avg_buy_price': 10, 'bought_at': '2026-10-01'})

        response = client.post(f'/api/v1/me/positions/{asset.id}/sell', json={'quantity': 3})

        assert response.status_code == 400
        assert response.get_json() == {'error': 'Nicht genug Anteile!'}


class TestBudgetRules:

    def test_paused_booking_reports_since_when(self, client, category):
        """Das Haushaltsbuch zählt eine pausierte Buchung in früheren Monaten weiter mit"""
        created = client.post('/api/v1/me/transactions', json={
            'category_id': category.id, 'amount': 10, 'date': '2026-01-01', 'is_recurring': True}).get_json()
        client.post(f"/api/v1/me/transactions/{created['transaction_id']}/toggle-pause")

        booking = client.get('/api/v1/me/transactions').get_json()[0]

        assert booking['is_paused'] is True
        assert booking['paused_at'] == date.today().isoformat()

    def test_category_with_transactions_cannot_be_deleted(self, client, category):
        """Sonst verlieren Buchungen ihre Kategorie und zählen falsch im Saldo"""
        client.post('/api/v1/me/transactions', json={'category_id': category.id, 'amount': 10, 'date': '2026-10-01'})

        by_child = client.delete(f'/api/v1/me/categories/{category.id}')
        by_parent = client.delete(f'/api/v1/me/categories/{category.parent_id}')

        assert by_child.status_code == by_parent.status_code == 409
        assert db.session.get(Category, category.id) is not None

    def test_empty_category_can_be_deleted(self, client, category):
        response = client.delete(f'/api/v1/me/categories/{category.parent_id}')

        assert response.status_code == 200
        assert Category.query.count() == 0


class TestSettings:

    def test_settings_saved_and_returned(self, client):
        response = client.put('/api/v1/me/settings', json={
            'risk_profile': 'balanced', 'investment_experience': 'beginner',
            'monthly_budget': '', 'investment_horizon': 'long-term'})

        assert response.status_code == 200
        me = client.get('/api/v1/me').get_json()
        assert me['risk_profile'] == 'balanced'
        assert me['monthly_budget'] is None
        assert 'password' not in me


class TestStoredRecommendations:

    @pytest.mark.parametrize('stored,expected', [
        ('["Streuen", "Kosten prüfen"]', ['Streuen', 'Kosten prüfen']),
        ('["Das geht\'s gut"]', ["Das geht's gut"]),
        # Altes Format: Python-Text - früher am Apostroph zerbrochen
        ("[\"Das geht's gut\", 'Kosten prüfen']", ["Das geht's gut", 'Kosten prüfen']),
        ('', []),
    ])
    def test_old_and_new_formats_are_read(self, stored, expected):
        assert parse_stored_list(stored) == expected


class TestGermanMessages:

    def test_empty_text_field(self, client):
        response = client.post('/api/v1/me/chat', json={'message': '   '})

        assert response.status_code == 400
        assert response.get_json()['fields']['message'] == 'darf nicht leer sein'


def test_trade_history_in_chronological_order(client, asset):
    """Kauf, Nachkauf und Verkauf erscheinen in der Historie in der
    Reihenfolge, in der sie passiert sind (neueste zuerst)"""
    client.post('/api/v1/me/positions', json={'asset_id': asset.id, 'quantity': 2, 'avg_buy_price': 10, 'bought_at': '2026-10-01'})
    client.post(f'/api/v1/me/positions/{asset.id}/buy', json={'quantity': 1, 'price': 12})
    client.post(f'/api/v1/me/positions/{asset.id}/sell', json={'quantity': 1, 'price': 15})

    history = client.get('/api/v1/me/asset-transactions').get_json()

    assert [entry['type'] for entry in history] == ['sell', 'buy', 'buy']
