"""
test_price_engine.py - Kurse und Wechselkurse laden, speichern und in Euro
umrechnen (market/service.py), die täglichen Jobs und ihre Admin-Endpoints.
yfinance ist durch FakeYahoo aus conftest.py ersetzt.
"""

import sys
import os
import threading
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack import jobs
from fintrack.budget.service import create_default_categories
from fintrack.insights.service import generate_insights_for_all_users
from fintrack.market import service
from fintrack.market.prices import get_current_price
from fintrack.models import (Asset, AssetTransaction, DailyInsight, Dividend, FxRate,
                             PriceHistory, Transaction, UserAsset, db)
from fintrack.portfolio.dividends import process_dividends_for_user

TODAY = date(2026, 10, 28)  # ein Mittwoch


def days_back(n):
    return TODAY - timedelta(days=n)


def make_asset(symbol, currency='EUR', **kwargs):
    kwargs.setdefault('metadata_updated_at', datetime.now())
    asset = Asset(name=symbol, symbol=symbol, currency=currency, asset_type='stock', **kwargs)
    db.session.add(asset)
    db.session.commit()
    return asset


def stored_prices(asset):
    rows = PriceHistory.query.filter_by(asset_id=asset.id).order_by(PriceHistory.date).all()
    return [(row.date.date(), row.price, row.currency) for row in rows]


class TestUpdatePrices:

    def test_new_asset_loads_one_year(self, app, fake_yahoo):
        asset = make_asset('SAP.DE')
        fake_yahoo.closes['SAP.DE'] = [(days_back(400), 1.0, 'EUR'), (days_back(365), 2.0, 'EUR'),
                                       (TODAY, 3.0, 'EUR')]

        assert service.update_asset_prices(asset, TODAY) == 2
        db.session.commit()

        assert stored_prices(asset) == [(days_back(365), 2.0, 'EUR'), (TODAY, 3.0, 'EUR')]

    def test_rolling_window_overwrites_last_days(self, app, fake_yahoo):
        """Ein Zwischenstand von gestern wird durch den Schlusskurs ersetzt"""
        asset = make_asset('SAP.DE')
        db.session.add(PriceHistory(asset_id=asset.id, date=datetime(2026, 10, 27), price=99.0, currency='EUR'))
        db.session.add(PriceHistory(asset_id=asset.id, date=datetime(2026, 9, 1), price=50.0, currency='EUR'))
        db.session.commit()
        fake_yahoo.closes['SAP.DE'] = [(date(2026, 9, 1), 1.0, 'EUR'), (date(2026, 10, 27), 100.0, 'EUR'),
                                       (TODAY, 101.0, 'EUR')]

        service.update_asset_prices(asset, TODAY)
        db.session.commit()

        # Nur die letzten 7 Tage werden abgefragt - ältere Kurse bleiben
        assert fake_yahoo.calls[-1] == ('SAP.DE', days_back(7), TODAY)
        assert stored_prices(asset) == [(date(2026, 9, 1), 50.0, 'EUR'), (date(2026, 10, 27), 100.0, 'EUR'),
                                        (TODAY, 101.0, 'EUR')]

    def test_missed_runs_are_caught_up(self, app, fake_yahoo):
        """Nach drei Wochen Pause wird ab dem letzten gespeicherten Tag geladen"""
        asset = make_asset('SAP.DE')
        db.session.add(PriceHistory(asset_id=asset.id, date=datetime(2026, 10, 1), price=1.0, currency='EUR'))
        db.session.commit()

        service.update_asset_prices(asset, TODAY)

        assert fake_yahoo.calls[-1] == ('SAP.DE', date(2026, 10, 2), TODAY)

    def test_update_all_prices_loads_fx_and_reports_unknown(self, app, fake_yahoo):
        make_asset('AAPL', currency=None, metadata_updated_at=None)
        make_asset('WEG')  # yfinance kennt es nicht mehr, Metadaten sind aber frisch
        make_asset('ALT', metadata_updated_at=None)
        fake_yahoo.add_stock('AAPL', currency='USD', exchange='NMS')
        fake_yahoo.closes['AAPL'] = [(TODAY, 200.0, 'USD')]
        fake_yahoo.closes['USDEUR=X'] = [(days_back(1), 0.9, 'USD'), (TODAY, 0.91, 'USD')]

        summary = service.update_all_prices(TODAY)

        aapl = Asset.query.filter_by(symbol='AAPL').one()
        assert (aapl.currency, aapl.exchange) == ('USD', 'NMS')
        assert summary['prices'] == 1
        assert summary['fx_rates'] == 2
        assert summary['errors'] == ['ALT: bei yfinance unbekannt']
        assert [(r.date, r.rate_to_eur) for r in FxRate.query.order_by(FxRate.date)] == \
            [(days_back(1), 0.9), (TODAY, 0.91)]

    def test_one_failing_asset_does_not_stop_the_run(self, app, fake_yahoo, monkeypatch):
        make_asset('KAPUTT')
        make_asset('SAP.DE')
        fake_yahoo.closes['SAP.DE'] = [(TODAY, 100.0, 'EUR')]
        original = fake_yahoo.fetch_daily_closes

        def flaky(symbol, start, end=None):
            if symbol == 'KAPUTT':
                raise RuntimeError('Zeitüberschreitung')
            return original(symbol, start, end)
        monkeypatch.setattr(service.yahoo, 'fetch_daily_closes', flaky)

        summary = service.update_all_prices(TODAY)

        assert summary['prices'] == 1
        assert summary['errors'] == ['KAPUTT: Zeitüberschreitung']


class TestEuroConversion:

    def test_fx_rate_uses_last_known_day(self, app):
        db.session.add_all([FxRate(currency='USD', date=date(2026, 10, 23), rate_to_eur=0.90),
                            FxRate(currency='USD', date=date(2026, 10, 26), rate_to_eur=0.92)])
        db.session.commit()
        table = service.FxTable('USD')

        assert table.rate_on(date(2026, 10, 25)) == 0.90  # Sonntag -> Freitagskurs
        assert table.rate_on(date(2026, 10, 26)) == 0.92
        assert table.rate_on(date(2026, 1, 1)) == 0.90    # vor dem ersten Kurs
        assert service.FxTable('EUR').rate_on(TODAY) == 1.0
        assert service.FxTable('CHF').rate_on(TODAY) is None

    def test_history_uses_each_days_own_rate(self, app):
        asset = make_asset('AAPL', currency='USD')
        db.session.add_all([
            PriceHistory(asset_id=asset.id, date=datetime(2026, 10, 23), price=100.0, currency='USD'),
            PriceHistory(asset_id=asset.id, date=datetime(2026, 10, 26), price=100.0, currency='USD'),
            FxRate(currency='USD', date=date(2026, 10, 23), rate_to_eur=0.90),
            FxRate(currency='USD', date=date(2026, 10, 26), rate_to_eur=0.95),
        ])
        db.session.commit()

        assert service.price_history_in_eur(asset) == [(date(2026, 10, 23), 90.0), (date(2026, 10, 26), 95.0)]
        assert service.price_in_eur_on(asset, date(2026, 10, 25)) == pytest.approx(90.0)

    def test_euro_listing_is_not_converted(self, app, fake_yahoo):
        """SAP.DE kostet in Euro - früher wurde fälschlich von Dollar umgerechnet"""
        asset = make_asset('SAP.DE')
        fake_yahoo.last_prices['SAP.DE'] = (240.5, 'EUR')

        assert get_current_price(asset) == 240.5

    def test_current_price_converts_with_latest_rate(self, app, fake_yahoo):
        asset = make_asset('VUSA.L', currency='GBP')
        fake_yahoo.last_prices['VUSA.L'] = (81.5, 'GBP')  # aus 8150 Pence
        db.session.add(FxRate(currency='GBP', date=date.today(), rate_to_eur=1.2))
        db.session.commit()

        assert get_current_price(asset) == 97.8

    def test_current_price_falls_back_without_quote(self, app):
        asset = make_asset('WEG')

        assert get_current_price(asset, unknown_type_default=12.0) == 12.0
        assert get_current_price(asset) is None

    def test_stale_fx_rate_is_fetched_live(self, app, fake_yahoo):
        db.session.add(FxRate(currency='USD', date=date.today() - timedelta(days=30), rate_to_eur=0.80))
        db.session.commit()
        fake_yahoo.last_prices['USDEUR=X'] = (0.93, 'EUR')

        assert service.latest_fx_rate('USD') == 0.93
        del fake_yahoo.last_prices['USDEUR=X']
        assert service.latest_fx_rate('USD') == 0.80


class TestDividends:

    def test_dividend_converted_with_rate_of_ex_day(self, app, make_user, fake_yahoo):
        user = make_user('a@test.com')
        create_default_categories(user.id)
        asset = make_asset('AAPL', currency='USD')
        bought = datetime(datetime.now().year, 1, 2)
        db.session.add_all([
            UserAsset(user_id=user.id, asset_id=asset.id, quantity=10, avg_buy_price=150, bought_at=bought,
                      status='owned'),
            AssetTransaction(user_id=user.id, asset_id=asset.id, type='buy', quantity=10, price=150, date=bought),
        ])
        db.session.commit()
        ex_day = date(datetime.now().year, 2, 10)
        fake_yahoo.dividends['AAPL'] = [(ex_day, 0.25)]
        fake_yahoo.closes['USDEUR=X'] = [(ex_day - timedelta(days=1), 0.8, 'USD'), (ex_day, 0.9, 'USD')]

        process_dividends_for_user(user.id)

        dividend = Dividend.query.one()
        assert dividend.amount_per_share == pytest.approx(0.225)
        assert dividend.total_amount == 2.25
        assert db.session.get(Transaction, dividend.transaction_id).amount == 2.25

        # Zweiter Lauf bucht nichts doppelt
        process_dividends_for_user(user.id)
        assert Dividend.query.count() == 1


class TestInsights:

    def test_only_one_insight_per_day(self, app, make_user):
        make_user('a@test.com')
        client = MagicMock()
        client.chat.completions.create.return_value.choices = [MagicMock(message=MagicMock(content='Alles gut.'))]

        assert generate_insights_for_all_users(client) == 1
        assert generate_insights_for_all_users(client) == 0
        assert DailyInsight.query.count() == 1
        assert client.chat.completions.create.call_count == 1


@pytest.fixture
def fresh_job_state():
    jobs._status.update(state='idle', job=None, started_at=None, finished_at=None, result=None, error=None)
    yield
    assert not jobs._lock.locked(), 'Ein Test hat die Job-Sperre nicht freigegeben'


class TestJobs:

    def test_daily_run_reports_each_step(self, app, fresh_job_state, monkeypatch):
        monkeypatch.setattr(jobs, 'update_all_prices', lambda: {'assets': 1, 'errors': []})
        monkeypatch.setattr(jobs, 'process_dividends_for_all_users', lambda: None)
        monkeypatch.setattr(jobs, 'generate_insights_for_all_users', lambda client: 2)
        monkeypatch.setattr(jobs, 'get_openai_client', lambda: None)

        assert jobs.start_job(app, 'daily', background=False)

        status = jobs.job_status()
        assert status['state'] == 'done'
        assert status['result'] == {'prices': {'assets': 1, 'errors': []},
                                    'dividends': {'dividends': 'geprüft'}, 'insights': {'insights': 2}}

    def test_failed_step_does_not_stop_later_steps(self, app, fresh_job_state, monkeypatch):
        def broken():
            raise RuntimeError('yfinance down')
        monkeypatch.setattr(jobs, 'update_all_prices', broken)
        monkeypatch.setattr(jobs, 'process_dividends_for_all_users', lambda: None)
        monkeypatch.setattr(jobs, 'generate_insights_for_all_users', lambda client: 0)
        monkeypatch.setattr(jobs, 'get_openai_client', lambda: None)

        jobs.start_job(app, 'daily', background=False)

        status = jobs.job_status()
        assert status['state'] == 'failed'
        assert status['result']['prices'] == {'error': 'yfinance down'}
        assert status['result']['insights'] == {'insights': 0}

    def test_second_start_is_refused_while_running(self, app, fresh_job_state, monkeypatch):
        release = threading.Event()
        monkeypatch.setattr(jobs, 'update_all_prices', lambda: release.wait(5) and {})

        assert jobs.start_job(app, 'prices')
        assert jobs.start_job(app, 'daily') is False
        assert jobs.job_status()['state'] == 'running'

        release.set()
        for _ in range(100):
            if not jobs._lock.locked():
                break
            threading.Event().wait(0.05)
        assert jobs.job_status()['state'] == 'done'


class TestJobRoutes:

    def test_start_returns_202_and_status_is_readable(self, app, fresh_job_state, monkeypatch):
        monkeypatch.setenv('ADMIN_API_KEY', 'geheim')
        started = []
        monkeypatch.setattr('fintrack.admin.routes.start_job', lambda flask_app, name: started.append(name) or True)
        client = app.test_client()

        response = client.post('/api/v1/admin/run-daily-jobs', headers={'X-Admin-Key': 'geheim'})
        assert response.status_code == 202
        assert started == ['daily']

        response = client.get('/api/v1/admin/jobs/status', headers={'X-Admin-Key': 'geheim'})
        assert response.status_code == 200
        assert response.get_json()['state'] == 'idle'

    def test_running_job_gives_409(self, app, fresh_job_state, monkeypatch):
        monkeypatch.setenv('ADMIN_API_KEY', 'geheim')
        monkeypatch.setattr('fintrack.admin.routes.start_job', lambda flask_app, name: False)

        response = app.test_client().post('/api/v1/admin/update-prices', headers={'X-Admin-Key': 'geheim'})

        assert response.status_code == 409

    def test_status_needs_key(self, app, monkeypatch):
        monkeypatch.setenv('ADMIN_API_KEY', 'geheim')

        assert app.test_client().get('/api/v1/admin/jobs/status').status_code == 403
