"""
test_portfolio_performance.py - Zeitgewichtete Depot-Rendite und
Vergleichsindex (portfolio/performance.py) samt Endpoint.
"""

from datetime import date, datetime, timedelta

import pytest

from fintrack.models import Asset, AssetTransaction, PriceHistory, UserAsset, db
from fintrack.portfolio.performance import BENCHMARK_SYMBOL, benchmark_asset, performance_series

MON = date(2026, 10, 19)  # Montag


def day(n):
    return MON + timedelta(days=n)


def make_asset(symbol, prices, currency='EUR'):
    asset = Asset(name=symbol, symbol=symbol, currency=currency, asset_type='stock')
    db.session.add(asset)
    db.session.flush()
    for n, price in prices.items():
        db.session.add(PriceHistory(asset_id=asset.id, date=datetime.combine(day(n), datetime.min.time()),
                                    price=price, currency=currency))
    db.session.commit()
    return asset


def buy(user, asset, quantity, n):
    db.session.add(AssetTransaction(user_id=user.id, asset_id=asset.id, type='buy', quantity=quantity,
                                    price=100.0, date=datetime.combine(day(n), datetime.min.time()) + timedelta(hours=12)))
    position = UserAsset.query.filter_by(user_id=user.id, asset_id=asset.id).first()
    if position:
        position.quantity += quantity
    else:
        db.session.add(UserAsset(user_id=user.id, asset_id=asset.id, quantity=quantity, avg_buy_price=100.0,
                                 bought_at=datetime.combine(day(n), datetime.min.time()), status='owned'))
    db.session.commit()


@pytest.fixture
def user(make_user):
    return make_user('a@test.com')


class TestPerformanceSeries:

    def test_buying_more_is_not_a_gain(self, app, user):
        # Kurs 100 → 110 → 110 → 121; am Tag 2 verzehnfacht sich der Bestand
        asset = make_asset('SAP.DE', {0: 100, 1: 110, 2: 110, 3: 121})
        buy(user, asset, 1, 0)
        buy(user, asset, 9, 2)

        series = performance_series(user.id, today=day(3))

        factors = [factor for _, factor, _ in series]
        assert factors == pytest.approx([1.0, 1.1, 1.1, 1.21])

    def test_mixes_positions_by_yesterdays_weight(self, app, user):
        a = make_asset('A.DE', {0: 100, 1: 120})   # +20 %
        b = make_asset('B.DE', {0: 100, 1: 90})    # -10 %
        buy(user, a, 1, 0)
        buy(user, b, 3, 0)

        series = performance_series(user.id, today=day(1))

        # 100 € in A, 300 € in B: (120 + 270) / 400
        assert series[-1][1] == pytest.approx(390 / 400)

    def test_benchmark_prices_ride_along(self, app, user):
        asset = make_asset('SAP.DE', {0: 100, 1: 100})
        make_asset(BENCHMARK_SYMBOL, {1: 80})
        buy(user, asset, 1, 0)

        series = performance_series(user.id, today=day(1))

        assert [bench for _, _, bench in series] == [None, 80.0]

    def test_empty_without_positions(self, app, user):
        assert performance_series(user.id, today=day(1)) == []


class TestBenchmarkAsset:

    def test_created_once_when_missing(self, app, fake_yahoo):
        fake_yahoo.add_stock(BENCHMARK_SYMBOL, asset_type='etf')
        fake_yahoo.closes[BENCHMARK_SYMBOL] = [(date.today() - timedelta(days=1), 95.0, 'EUR')]

        first = benchmark_asset()
        again = benchmark_asset()

        assert first is not None and first.id == again.id
        assert Asset.query.filter_by(symbol=BENCHMARK_SYMBOL).count() == 1
        assert PriceHistory.query.filter_by(asset_id=first.id).count() == 1

    def test_unknown_at_yahoo_gives_none(self, app):
        assert benchmark_asset() is None


class TestPerformanceRoute:

    def test_returns_points_and_benchmark(self, user, login_client):
        asset = make_asset('SAP.DE', {0: 100})
        make_asset(BENCHMARK_SYMBOL, {0: 80})
        buy(user, asset, 1, 0)

        data = login_client('a@test.com').get('/api/v1/me/portfolio/performance').get_json()

        assert data['benchmark'] == {'name': 'MSCI World', 'symbol': BENCHMARK_SYMBOL}
        assert data['points'][0] == {'date': day(0).isoformat(), 'portfolio': 1.0, 'benchmark': 80.0}
        assert data['points'][-1]['date'] == date.today().isoformat()

    def test_without_benchmark_prices(self, user, login_client):
        asset = make_asset('SAP.DE', {0: 100})
        buy(user, asset, 1, 0)

        data = login_client('a@test.com').get('/api/v1/me/portfolio/performance').get_json()

        assert data['benchmark'] is None

    def test_login_required(self, app):
        assert app.test_client().get('/api/v1/me/portfolio/performance').status_code == 401
