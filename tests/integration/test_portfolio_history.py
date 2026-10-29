"""
test_portfolio_history.py - Bestand und Portfolio-Wert in der
Vergangenheit, rekonstruiert aus Käufen und Verkäufen
(portfolio/history.py), und der Wertverlauf-Endpoint.
"""

import sys
import os
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.insights.service import calculate_portfolio_value_at
from fintrack.models import Asset, AssetTransaction, FxRate, PriceHistory, UserAsset, db
from fintrack.portfolio.dividends import calculate_shares_held_at
from fintrack.portfolio.history import Holdings, portfolio_value_series

MON = date(2026, 10, 19)  # Montag


def day(n):
    """Tag n nach dem Montag MON."""
    return MON + timedelta(days=n)


def at(n, hour=12):
    return datetime.combine(day(n), datetime.min.time()) + timedelta(hours=hour)


def make_asset(symbol, currency='EUR', prices=None):
    """Asset mit Schlusskursen {Tag-Nr: Kurs} an Handelstagen."""
    asset = Asset(name=symbol, symbol=symbol, currency=currency, asset_type='stock')
    db.session.add(asset)
    db.session.flush()
    for n, price in (prices or {}).items():
        db.session.add(PriceHistory(asset_id=asset.id, date=datetime.combine(day(n), datetime.min.time()),
                                    price=price, currency=currency))
    db.session.commit()
    return asset


def trade(user, asset, kind, quantity, n, price=100.0):
    db.session.add(AssetTransaction(user_id=user.id, asset_id=asset.id, type=kind, quantity=quantity,
                                    price=price, date=at(n)))


def position(user, asset, quantity, bought_n=None, avg=100.0):
    db.session.add(UserAsset(user_id=user.id, asset_id=asset.id, quantity=quantity, avg_buy_price=avg,
                             bought_at=at(bought_n) if bought_n is not None else None,
                             status='owned' if quantity else 'sold'))
    db.session.commit()


@pytest.fixture
def user(make_user):
    return make_user('a@test.com')


class TestHoldings:

    def test_buy_in_the_middle_counts_only_from_that_day(self, app, user):
        asset = make_asset('SAP.DE')
        trade(user, asset, 'buy', 10, 2)
        position(user, asset, 10, 2)
        holdings = Holdings(user.id)

        assert holdings.quantity_on(asset.id, day(1)) == 0
        assert holdings.quantity_on(asset.id, day(2)) == 10
        assert holdings.quantity_on(asset.id, day(30)) == 10

    def test_partial_and_full_sale(self, app, user):
        asset = make_asset('SAP.DE')
        trade(user, asset, 'buy', 10, 0)
        trade(user, asset, 'sell', 4, 3)
        trade(user, asset, 'sell', 6, 5)
        position(user, asset, 0, 0)
        holdings = Holdings(user.id)

        assert [holdings.quantity_on(asset.id, day(n)) for n in range(7)] == [10, 10, 10, 6, 6, 0, 0]

    def test_float_rest_after_full_sale_is_zero(self, app, user):
        asset = make_asset('BTC-EUR')
        for n in range(3):
            trade(user, asset, 'buy', 0.1, n)
        trade(user, asset, 'sell', 0.3, 4)
        position(user, asset, 0, 0)

        assert Holdings(user.id).quantity_on(asset.id, day(4)) == 0

    def test_legacy_position_without_transactions(self, app, user):
        """Positionen aus der Zeit vor der Protokollierung zählen ab ihrem Kaufdatum"""
        asset = make_asset('SAP.DE')
        position(user, asset, 5, bought_n=3)
        holdings = Holdings(user.id)

        assert holdings.quantity_on(asset.id, day(2)) == 0
        assert holdings.quantity_on(asset.id, day(3)) == 5

    def test_legacy_rest_before_logged_trades(self, app, user):
        """5 Stück Altbestand, danach 2 protokollierte Käufe -> Anfangsbestand 5"""
        asset = make_asset('SAP.DE')
        trade(user, asset, 'buy', 2, 4)
        position(user, asset, 7, bought_n=1)
        holdings = Holdings(user.id)

        assert holdings.quantity_on(asset.id, day(0)) == 0
        assert holdings.quantity_on(asset.id, day(1)) == 5
        assert holdings.quantity_on(asset.id, day(4)) == 7

    def test_other_users_trades_are_ignored(self, app, user, make_user):
        other = make_user('b@test.com')
        asset = make_asset('SAP.DE')
        trade(other, asset, 'buy', 99, 0)
        position(other, asset, 99, 0)

        assert Holdings(user.id).quantity_on(asset.id, day(5)) == 0

    def test_dividends_use_the_same_count(self, app, user):
        asset = make_asset('SAP.DE')
        trade(user, asset, 'buy', 10, 0)
        trade(user, asset, 'sell', 10, 5)
        position(user, asset, 0, 0)

        assert calculate_shares_held_at(user.id, asset.id, at(2)) == 10
        assert calculate_shares_held_at(user.id, asset.id, at(6)) == 0


class TestValueSeries:

    def test_value_follows_real_quantities(self, app, user):
        # Kurse Mo-Fr, Wochenende ohne Kurs
        asset = make_asset('SAP.DE', prices={0: 100, 1: 101, 2: 102, 3: 103, 4: 104, 7: 110})
        trade(user, asset, 'buy', 10, 1)
        trade(user, asset, 'sell', 5, 3)
        position(user, asset, 5, 1)

        series = dict(portfolio_value_series(user.id, today=day(7)))

        assert day(0) not in series            # vor dem Kauf
        assert series[day(1)] == 1010.0         # 10 x 101
        assert series[day(3)] == 515.0          # nach Teilverkauf: 5 x 103
        assert series[day(5)] == 520.0          # Samstag: Freitagskurs 104
        assert series[day(7)] == 550.0

    def test_sold_position_still_counts_in_the_past(self, app, user):
        sold = make_asset('ALT', prices={0: 50, 2: 50})
        kept = make_asset('NEU', prices={0: 10, 2: 10})
        trade(user, sold, 'buy', 2, 0)
        trade(user, sold, 'sell', 2, 2)
        trade(user, kept, 'buy', 1, 0)
        position(user, sold, 0, 0)
        position(user, kept, 1, 0)

        series = dict(portfolio_value_series(user.id, today=day(2)))

        assert series[day(1)] == 110.0
        assert series[day(2)] == 10.0

    def test_everything_sold_shows_zero(self, app, user):
        asset = make_asset('SAP.DE', prices={0: 100})
        trade(user, asset, 'buy', 1, 0)
        trade(user, asset, 'sell', 1, 1)
        position(user, asset, 0, 0)

        assert portfolio_value_series(user.id, today=day(2)) == [(day(0), 100.0), (day(1), 0.0), (day(2), 0.0)]

    def test_foreign_currency_uses_rate_of_each_day(self, app, user):
        asset = make_asset('AAPL', currency='USD', prices={0: 100, 1: 100})
        db.session.add_all([FxRate(currency='USD', date=day(0), rate_to_eur=0.9),
                            FxRate(currency='USD', date=day(1), rate_to_eur=0.8)])
        trade(user, asset, 'buy', 2, 0)
        position(user, asset, 2, 0)

        assert portfolio_value_series(user.id, today=day(1)) == [(day(0), 180.0), (day(1), 160.0)]

    def test_no_positions(self, app, user):
        assert portfolio_value_series(user.id) == []

    def test_insights_value_uses_real_quantity(self, app, user):
        asset = make_asset('SAP.DE', prices={0: 100, 7: 120})
        trade(user, asset, 'buy', 10, 6)
        position(user, asset, 10, 6)

        assert calculate_portfolio_value_at(user.id, at(0)) == 0
        assert calculate_portfolio_value_at(user.id, at(7)) == pytest.approx(1200.0)


class TestHistoryRoute:

    def test_returns_daily_values(self, user, login_client):
        asset = make_asset('SAP.DE', prices={0: 100})
        trade(user, asset, 'buy', 3, 0)
        position(user, asset, 3, 0)
        client = login_client('a@test.com')

        data = client.get('/api/v1/me/portfolio/history').get_json()

        assert data[0] == {'date': day(0).isoformat(), 'value': 300.0}
        assert data[-1]['date'] == date.today().isoformat()

    def test_login_required(self, app):
        assert app.test_client().get('/api/v1/me/portfolio/history').status_code == 401
