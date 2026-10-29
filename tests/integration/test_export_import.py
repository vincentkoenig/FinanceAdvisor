"""
test_export_import.py - Tests für den Export und Import aller eigenen
Daten (GET /api/v1/me/export, POST /api/v1/me/import).

Kernstück ist der Hin-und-zurück-Test: Ein Konto mit Daten aller Art wird
exportiert, in ein frisches Konto importiert und erneut exportiert - beide
Dateien müssen bis auf den Zeitstempel identisch sein. Damit ist
sichergestellt, dass beim Umzug in eine andere Datenbank nichts verloren geht.
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.budget.service import create_default_categories
from fintrack.extensions import db
from fintrack.models import (Asset, AssetTransaction, Category, ChatHistory, DailyInsight, Dividend,
                             PortfolioAnalysis, SavingsPlan, Transaction, UserAsset, Watchlist)


@pytest.fixture(autouse=True)
def no_price_downloads(mocker):
    """Keine echten Kursabfragen beim Import neuer Assets."""
    return mocker.patch('fintrack.account.routes.load_price_history', return_value=0)


@pytest.fixture
def full_account(make_user):
    """Nutzer A mit Daten in jedem Bereich, inkl. Sonderfällen."""
    user = make_user('a@test.com')
    user.risk_profile = 'balanced'
    user.monthly_budget = 750.0
    create_default_categories(user.id)

    own_main = Category(user_id=user.id, name='Reisen', type='variable_expense')
    db.session.add(own_main)
    db.session.flush()
    own_sub = Category(user_id=user.id, name='Flüge & Hotels', type='variable_expense', parent_id=own_main.id)
    dividend_category = Category.query.filter_by(user_id=user.id, name='Dividenden').one()
    db.session.add(own_sub)
    db.session.flush()

    apple = Asset(name='Apple Inc.', symbol='AAPL', asset_type='stock', currency='EUR')
    btc = Asset(name='Bitcoin', symbol='BTC-EUR', asset_type='stock', currency='EUR')
    db.session.add_all([apple, btc])
    db.session.flush()

    dividend_booking = Transaction(user_id=user.id, category_id=dividend_category.id, amount=1.23,
                                   description='Dividende Apple', date=datetime(2026, 8, 15))
    db.session.add(dividend_booking)
    db.session.flush()

    db.session.add_all([
        Transaction(user_id=user.id, category_id=own_sub.id, amount=499.99, description='Lissabon "Frühling"',
                    date=datetime(2026, 4, 2)),
        Transaction(user_id=user.id, category_id=dividend_category.id, amount=3000, date=datetime(2026, 1, 1),
                    is_recurring=True, is_paused=True, paused_at=datetime(2026, 9, 30, 12, 0),
                    end_date=datetime(2027, 12, 31)),
        UserAsset(user_id=user.id, asset_id=apple.id, quantity=3.5, avg_buy_price=181.25,
                  bought_at=datetime(2026, 3, 1), status='owned'),
        UserAsset(user_id=user.id, asset_id=btc.id, quantity=0, avg_buy_price=60000,
                  bought_at=datetime(2026, 2, 1), status='sold'),
        AssetTransaction(user_id=user.id, asset_id=apple.id, type='buy', quantity=3.5, price=181.25,
                         date=datetime(2026, 3, 1, 10, 30)),
        AssetTransaction(user_id=user.id, asset_id=btc.id, type='sell', quantity=0.01, price=65000.5,
                         date=datetime(2026, 5, 1)),
        SavingsPlan(user_id=user.id, asset_id=apple.id, amount=100, day_of_month=15,
                    start_date=datetime(2026, 1, 1), last_executed=datetime(2026, 10, 15), active=True),
        Watchlist(user_id=user.id, asset_id=btc.id, price_added=58000, added_at=datetime(2026, 6, 1)),
        Dividend(user_id=user.id, asset_id=apple.id, ex_dividend_date=datetime(2026, 8, 15),
                 amount_per_share=0.3514, shares_held=3.5, total_amount=1.23,
                 transaction_id=dividend_booking.id, booked_at=datetime(2026, 8, 16)),
        ChatHistory(user_id=user.id, role='user', message='Was ist ein ETF?', created_at=datetime(2026, 7, 1, 9)),
        ChatHistory(user_id=user.id, role='assistant', message='Ein **Fonds**, der …',
                    created_at=datetime(2026, 7, 1, 9, 0, 5)),
        PortfolioAnalysis(user_id=user.id, total_value=634.38, risk_assessment='mittel', diversification_score=4,
                          summary='Konzentriert', recommendations=json.dumps(["Das geht's besser streuen"]),
                          allocation=json.dumps([{"asset": "Apple", "value": 634.38, "percentage": 100.0}]),
                          created_at=datetime(2026, 10, 1)),
        DailyInsight(user_id=user.id, content='Dein Depot liegt 2 % im Plus.', created_at=datetime(2026, 10, 2)),
    ])
    db.session.commit()
    return user


def export_of(client):
    response = client.get('/api/v1/me/export')
    assert response.status_code == 200
    return json.loads(response.data)


def without_timestamp(export):
    return {key: value for key, value in export.items() if key != 'exported_at'}


class TestExport:

    def test_export_is_a_download_with_all_sections(self, full_account, login_client):
        client = login_client('a@test.com')

        response = client.get('/api/v1/me/export')
        data = json.loads(response.data)

        assert 'attachment' in response.headers['Content-Disposition']
        assert response.headers['Cache-Control'] == 'no-store'
        assert data['format'] == 'fintrack-export' and data['version'] == 1
        assert len(data['transactions']) == 3
        assert len(data['positions']) == 2
        assert {a['symbol'] for a in data['assets']} == {'AAPL', 'BTC-EUR'}
        assert data['analyses'][0]['recommendations'] == ["Das geht's besser streuen"]
        assert data['profile']['monthly_budget'] == 750.0

    def test_export_contains_no_password_or_email(self, full_account, login_client):
        raw = login_client('a@test.com').get('/api/v1/me/export').data

        assert b'a@test.com' not in raw
        assert b'pbkdf2' not in raw and b'scrypt' not in raw


class TestRoundTrip:

    def test_export_import_export_is_identical(self, full_account, make_user, login_client):
        """Kein Feld geht beim Umzug in ein anderes Konto verloren"""
        original = export_of(login_client('a@test.com'))

        new_user = make_user('b@test.com')
        create_default_categories(new_user.id)  # wie nach einer Registrierung
        client_b = login_client('b@test.com')
        response = client_b.post('/api/v1/me/import', json=original)
        assert response.status_code == 201, response.get_json()

        assert without_timestamp(export_of(client_b)) == without_timestamp(original)

    def test_import_into_other_database_creates_missing_assets(self, full_account, make_user,
                                                               login_client, no_price_downloads):
        """Assets, die es in der Zieldatenbank nicht gibt, werden angelegt
        und ihre Kurshistorie geladen"""
        export = export_of(login_client('a@test.com'))
        export['assets'].append({'ref': 99, 'symbol': 'NEU', 'name': 'Neue Aktie AG'})
        export['watchlist'].append({'asset_ref': 99})
        make_user('b@test.com')

        response = login_client('b@test.com').post('/api/v1/me/import', json=export)

        assert response.status_code == 201
        assert Asset.query.filter_by(symbol='NEU').count() == 1
        assert Asset.query.filter_by(symbol='AAPL').count() == 1  # vorhandenes wiederverwendet
        no_price_downloads.assert_called_once()


class TestImportSafety:

    def test_only_into_empty_account(self, full_account, login_client):
        """In ein Konto mit Daten wird nicht importiert - sonst Dubletten"""
        client = login_client('a@test.com')
        export = export_of(client)

        response = client.post('/api/v1/me/import', json=export)

        assert response.status_code == 409
        assert Transaction.query.filter_by(user_id=full_account.id).count() == 3

    @pytest.mark.parametrize('payload,message', [
        ({'format': 'etwas-anderes', 'version': 1}, 'keine FinTrack-Exportdatei'),
        ({'format': 'fintrack-export', 'version': 2}, 'nicht unterstützt'),
    ])
    def test_rejects_foreign_or_unknown_files(self, make_user, login_client, payload, message):
        make_user('b@test.com')

        response = login_client('b@test.com').post('/api/v1/me/import', json=payload)

        assert response.status_code == 400
        assert message in response.get_json()['error']

    def test_broken_reference_changes_nothing(self, full_account, make_user, login_client):
        """Eine Datei mit kaputtem Verweis wird komplett abgelehnt -
        die vorhandenen Kategorien bleiben unangetastet"""
        export = export_of(login_client('a@test.com'))
        export['transactions'][0]['category_ref'] = 9999
        user_b = make_user('b@test.com')
        create_default_categories(user_b.id)
        categories_before = Category.query.filter_by(user_id=user_b.id).count()

        response = login_client('b@test.com').post('/api/v1/me/import', json=export)

        assert response.status_code == 400
        assert 'unbekannte Kategorie' in response.get_json()['error']
        assert Category.query.filter_by(user_id=user_b.id).count() == categories_before

    def test_failure_during_import_rolls_back_everything(self, full_account, make_user, login_client, mocker):
        """Bricht das Speichern mittendrin ab, bleibt das Konto wie vorher"""
        export = export_of(login_client('a@test.com'))
        user_b = make_user('b@test.com')
        create_default_categories(user_b.id)
        categories_before = Category.query.filter_by(user_id=user_b.id).count()
        client_b = login_client('b@test.com')
        mocker.patch('fintrack.account.transfer._find_or_create_asset', side_effect=RuntimeError('DB weg'))

        with pytest.raises(RuntimeError):
            client_b.post('/api/v1/me/import', json=export)

        db.session.expire_all()
        assert Category.query.filter_by(user_id=user_b.id).count() == categories_before
        assert Transaction.query.filter_by(user_id=user_b.id).count() == 0

    def test_too_large_upload_rejected(self, app, make_user, login_client, monkeypatch):
        make_user('b@test.com')
        client = login_client('b@test.com')
        monkeypatch.setitem(app.config, 'MAX_CONTENT_LENGTH', 1000)

        response = client.post('/api/v1/me/import', json={'format': 'fintrack-export', 'padding': 'x' * 2000})

        assert response.status_code == 413
        assert 'zu groß' in response.get_json()['error']
