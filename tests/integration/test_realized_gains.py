"""
test_realized_gains.py - Kaufposten nach FIFO, realisierte Gewinne und die
Steuer-Schätzung (portfolio/lots.py) samt Endpoints und Chat-Tool.
"""

from datetime import date, datetime

import pytest

from fintrack.models import Asset, AssetTransaction, Dividend, UserAsset, db
from fintrack.portfolio.lots import build_book, buy_price, held_over_a_year, realized_overview


def tx(kind, quantity, price, day, id_=None):
    return AssetTransaction(id=id_, type=kind, quantity=quantity, price=price,
                            date=datetime.combine(day, datetime.min.time()))


def make_asset(symbol, asset_type='stock'):
    asset = Asset(name=symbol, symbol=symbol, currency='EUR', asset_type=asset_type)
    db.session.add(asset)
    db.session.commit()
    return asset


def trade(user, asset, kind, quantity, price, day):
    """Bucht wie record_buy/record_sell: Historie plus Bestand der Position."""
    db.session.add(AssetTransaction(user_id=user.id, asset_id=asset.id, type=kind, quantity=quantity,
                                    price=price, date=datetime.combine(day, datetime.min.time())))
    position = UserAsset.query.filter_by(user_id=user.id, asset_id=asset.id).first()
    change = quantity if kind == 'buy' else -quantity
    if position:
        position.quantity += change
    else:
        db.session.add(UserAsset(user_id=user.id, asset_id=asset.id, quantity=change, avg_buy_price=price,
                                 bought_at=datetime.combine(day, datetime.min.time()), status='owned'))
    db.session.commit()


@pytest.fixture
def user(make_user):
    return make_user('a@test.com')


class TestBuildBook:

    def test_sale_uses_oldest_lot_first(self):
        lots, sales = build_book([
            tx('buy', 10, 100, date(2024, 1, 1), 1),
            tx('buy', 10, 200, date(2025, 1, 1), 2),
            tx('sell', 15, 250, date(2026, 1, 1), 3),
        ])

        assert [(s.quantity, s.unit_cost) for s in sales] == [(10, 100), (5, 200)]
        assert sum(s.gain for s in sales) == pytest.approx(10 * 150 + 5 * 50)
        assert [(l.quantity, l.unit_cost) for l in lots] == [(5, 200)]

    def test_buy_price_differs_from_average_after_partial_sale(self):
        lots, _ = build_book([
            tx('buy', 10, 100, date(2024, 1, 1), 1),
            tx('buy', 10, 200, date(2025, 1, 1), 2),
            tx('sell', 10, 150, date(2026, 1, 1), 3),
        ])

        # Durchschnitt wäre 150, nach FIFO sind nur noch die Stücke zu 200 übrig
        assert buy_price(lots) == pytest.approx(200)

    def test_units_without_history_become_the_oldest_lot(self):
        position = UserAsset(quantity=15, avg_buy_price=80, bought_at=datetime(2020, 5, 1))
        lots, sales = build_book([tx('buy', 10, 100, date(2024, 1, 1), 1),
                                  tx('sell', 5, 120, date(2025, 1, 1), 2)], position)

        # 10 Stücke ohne Buchung zum Durchschnittspreis 80; der Verkauf verbraucht sie zuerst
        assert sales[0].unit_cost == 80 and sales[0].bought_on == date(2020, 5, 1)
        assert [(l.quantity, l.unit_cost, l.opening) for l in lots] == [(5, 80, True), (10, 100, False)]

    def test_selling_more_than_bought_has_no_gain(self):
        _, sales = build_book([tx('sell', 3, 50, date(2025, 1, 1), 1)])

        assert sales[0].bought_on is None and sales[0].gain == 0

    def test_float_dust_does_not_leave_a_lot(self):
        lots, _ = build_book([tx('buy', 0.0193, 100, date(2025, 1, 1), i) for i in range(1, 21)]
                             + [tx('sell', 0.386, 110, date(2025, 6, 1), 99)])

        assert lots == []


class TestCryptoHoldingPeriod:

    def test_exactly_one_year_is_not_enough(self):
        assert not held_over_a_year(date(2025, 3, 10), date(2026, 3, 10))
        assert held_over_a_year(date(2025, 3, 10), date(2026, 3, 11))


class TestRealizedOverview:

    def test_allowance_is_filled_by_gains_and_dividends(self, app, user):
        etf = make_asset('IWDA.AS', 'etf')
        trade(user, etf, 'buy', 10, 100, date(2026, 1, 5))
        trade(user, etf, 'sell', 10, 160, date(2026, 6, 1))
        db.session.add(Dividend(user_id=user.id, asset_id=etf.id, ex_dividend_date=datetime(2026, 3, 1),
                                amount_per_share=1, shares_held=100, total_amount=100))
        db.session.commit()

        result = realized_overview(user.id, 2026)

        securities = result["securities"]
        assert securities["other_gains"] == 600 and securities["dividends"] == 100
        assert securities["allowance_used"] == 700 and securities["allowance_left"] == 300
        assert len(result["sales"]) == 1 and result["sales"][0]["gain"] == 600

    def test_stock_losses_do_not_offset_etf_gains(self, app, user):
        stock = make_asset('SAP.DE')
        etf = make_asset('IWDA.AS', 'etf')
        trade(user, stock, 'buy', 10, 100, date(2026, 1, 5))
        trade(user, stock, 'sell', 10, 50, date(2026, 2, 1))
        trade(user, etf, 'buy', 10, 100, date(2026, 1, 5))
        trade(user, etf, 'sell', 10, 130, date(2026, 2, 1))

        securities = realized_overview(user.id, 2026)["securities"]

        assert securities["taxable"] == 300
        assert securities["stock_loss_carried"] == 500

    def test_etf_losses_offset_stock_gains(self, app, user):
        stock = make_asset('SAP.DE')
        etf = make_asset('IWDA.AS', 'etf')
        trade(user, stock, 'buy', 10, 100, date(2026, 1, 5))
        trade(user, stock, 'sell', 10, 200, date(2026, 2, 1))
        trade(user, etf, 'buy', 10, 100, date(2026, 1, 5))
        trade(user, etf, 'sell', 10, 70, date(2026, 2, 1))

        assert realized_overview(user.id, 2026)["securities"]["taxable"] == 700

    def test_crypto_is_split_by_holding_period(self, app, user):
        btc = make_asset('BTC-EUR', 'crypto')
        trade(user, btc, 'buy', 1, 20000, date(2024, 1, 1))
        trade(user, btc, 'buy', 1, 50000, date(2026, 1, 1))
        trade(user, btc, 'sell', 2, 60000, date(2026, 6, 1))

        result = realized_overview(user.id, 2026)

        assert result["crypto"]["tax_free_gains"] == 40000
        assert result["crypto"]["taxable_gains"] == 10000 and result["crypto"]["over_limit"]
        assert {row["tax_free"] for row in result["sales"]} == {True, False}
        # Krypto zählt nicht zum Sparerpauschbetrag
        assert result["securities"]["taxable"] == 0

    def test_only_the_requested_year_counts(self, app, user):
        etf = make_asset('IWDA.AS', 'etf')
        trade(user, etf, 'buy', 10, 100, date(2024, 1, 5))
        trade(user, etf, 'sell', 5, 120, date(2025, 2, 1))
        trade(user, etf, 'sell', 5, 140, date(2026, 2, 1))

        result = realized_overview(user.id, 2025)

        assert result["securities"]["other_gains"] == 100
        assert {2026, 2025} <= set(result["years"])


class TestEndpoints:

    def test_positions_report_the_fifo_buy_price(self, app, user, login_client, mocker):
        mocker.patch('fintrack.portfolio.routes.get_current_price', return_value=None)
        stock = make_asset('SAP.DE')
        trade(user, stock, 'buy', 10, 100, date(2024, 1, 1))
        trade(user, stock, 'buy', 10, 200, date(2025, 1, 1))
        trade(user, stock, 'sell', 10, 150, date(2026, 1, 1))

        positions = login_client('a@test.com').get('/api/v1/me/positions').get_json()

        assert positions[0]["buy_price"] == 200

    def test_lots_of_a_position(self, app, user, login_client, mocker):
        mocker.patch('fintrack.portfolio.routes.get_current_price', return_value=150.0)
        stock = make_asset('SAP.DE')
        trade(user, stock, 'buy', 10, 100, date(2024, 1, 1))
        trade(user, stock, 'buy', 5, 200, date(2025, 1, 1))

        body = login_client('a@test.com').get(f'/api/v1/me/positions/{stock.id}/lots').get_json()

        assert [(l["bought_on"], l["quantity"], l["gain"]) for l in body["lots"]] == [
            ('2024-01-01', 10, 500), ('2025-01-01', 5, -250)]
        assert body["lots"][0]["tax_free_from"] is None

    def test_lots_of_someone_elses_position_are_not_found(self, app, user, make_user, login_client, mocker):
        mocker.patch('fintrack.portfolio.routes.get_current_price', return_value=150.0)
        stock = make_asset('SAP.DE')
        trade(user, stock, 'buy', 10, 100, date(2024, 1, 1))
        make_user('b@test.com')

        response = login_client('b@test.com').get(f'/api/v1/me/positions/{stock.id}/lots')

        assert response.status_code == 404

    def test_realized_gains_endpoint(self, app, user, login_client):
        etf = make_asset('IWDA.AS', 'etf')
        trade(user, etf, 'buy', 10, 100, date(2025, 1, 5))
        trade(user, etf, 'sell', 10, 110, date(2025, 6, 1))
        client = login_client('a@test.com')

        body = client.get('/api/v1/me/realized-gains?year=2025').get_json()

        assert body["year"] == 2025 and body["securities"]["other_gains"] == 100
        assert client.get('/api/v1/me/realized-gains?year=abc').status_code == 400

    def test_married_users_get_the_joint_allowance(self, app, user, login_client):
        etf = make_asset('IWDA.AS', 'etf')
        trade(user, etf, 'buy', 10, 100, date(2026, 1, 5))
        trade(user, etf, 'sell', 10, 250, date(2026, 6, 1))
        client = login_client('a@test.com')

        single = client.get('/api/v1/me/realized-gains?year=2026').get_json()["securities"]
        assert single["allowance"] == 1000 and single["above_allowance"] == 500 and not single["joint"]

        response = client.put('/api/v1/me/tax-settings', json={'tax_joint': True})
        assert response.status_code == 200 and client.get('/api/v1/me').get_json()["tax_joint"] is True

        joint = client.get('/api/v1/me/realized-gains?year=2026').get_json()["securities"]
        assert joint["allowance"] == 2000 and joint["allowance_left"] == 500 and joint["joint"]

    def test_tax_settings_need_a_boolean(self, app, user, login_client):
        response = login_client('a@test.com').put('/api/v1/me/tax-settings', json={'tax_joint': 'vielleicht'})

        assert response.status_code == 400

    def test_tax_setting_does_not_touch_the_investment_profile(self, app, user, login_client):
        user.risk_profile = 'growth'
        db.session.commit()

        login_client('a@test.com').put('/api/v1/me/tax-settings', json={'tax_joint': True})

        assert db.session.get(type(user), user.id).risk_profile == 'growth'

    def test_chat_offers_the_realized_gains_tool(self):
        from fintrack.chat.tools import tools

        assert 'get_realized_gains' in [t["function"]["name"] for t in tools]
