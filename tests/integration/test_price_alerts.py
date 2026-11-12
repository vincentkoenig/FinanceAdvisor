"""
test_price_alerts.py - Kursprüfung tagsüber (push/alerts.py): starke Bewegungen einer
Position und des Depots, Watchlist-Zielkurse, Ruhezeit, und dass eine Prüfung ohne
Treffer die Datenbank nicht anfasst. Live-Kurse kommen aus FakeYahoo, der Versand an
Google/Apple ist ersetzt.
"""

import sys
import os
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from sqlalchemy import event

from fintrack.extensions import db
from fintrack.models import Asset, FxRate, PriceHistory, PushLog, PushSubscription, UserAsset, Watchlist
from fintrack.push import alerts, service

TODAY = date(2026, 11, 12)
NOON = datetime(2026, 11, 12, 12, 0)


@pytest.fixture(autouse=True)
def push_ready(monkeypatch):
    public, private = service.generate_vapid_keys()
    monkeypatch.setenv('VAPID_PUBLIC_KEY', public)
    monkeypatch.setenv('VAPID_PRIVATE_KEY', private)
    delivered = []
    monkeypatch.setattr(service, '_deliver', lambda sub, payload, key: delivered.append(payload) or 201)
    alerts._state.update(snapshot=None, dirty=True)
    yield delivered
    alerts._state.update(snapshot=None, dirty=True)


@pytest.fixture
def user(make_user):
    user = make_user('a@test.com')
    db.session.add(PushSubscription(user_id=user.id, endpoint='https://push.example.com/1', p256dh='B', auth='a'))
    db.session.commit()
    return user


def holding(user, symbol, quantity, previous_close, currency='EUR', name=None, closed_days_ago=1):
    asset = Asset(name=name or symbol, symbol=symbol, currency=currency, asset_type='stock')
    db.session.add(asset)
    db.session.commit()
    db.session.add_all([
        UserAsset(user_id=user.id, asset_id=asset.id, quantity=quantity, avg_buy_price=1, status='owned'),
        PriceHistory(asset_id=asset.id, date=datetime.combine(TODAY - timedelta(days=closed_days_ago), datetime.min.time()),
                     price=previous_close, currency=currency),
    ])
    db.session.commit()
    return asset


def check(now=NOON):
    return alerts.check_price_alerts(now=now, today=TODAY)


class TestPositionMoves:

    def test_strong_move_is_announced_once_per_direction(self, user, fake_yahoo, push_ready):
        holding(user, 'TSLA', 1, 100.0, currency='USD', name='Tesla')
        db.session.add(FxRate(currency='USD', date=TODAY, rate_to_eur=0.9))
        db.session.commit()
        fake_yahoo.last_prices['TSLA'] = (94.0, 'USD')

        assert check()['moves'] == 1
        check()
        assert [m['title'] for m in push_ready] == ['Tesla heute deutlich im Minus']
        assert push_ready[0]['body'] == 'Mehr als 5 % unter dem letzten Schlusskurs.'

        fake_yahoo.last_prices['TSLA'] = (106.0, 'USD')
        check()
        assert push_ready[-1]['title'] == 'Tesla heute deutlich im Plus'
        assert len(push_ready) == 2

    def test_small_move_stays_quiet(self, user, fake_yahoo, push_ready):
        holding(user, 'SAP.DE', 1, 100.0)
        fake_yahoo.last_prices['SAP.DE'] = (104.9, 'EUR')

        check()

        assert push_ready == []

    def test_stale_close_is_not_compared(self, user, fake_yahoo, push_ready):
        """Ist der Kurs-Lauf eine Woche ausgefallen, wäre jede Bewegung ein Fehlalarm"""
        holding(user, 'SAP.DE', 1, 100.0, closed_days_ago=9)
        fake_yahoo.last_prices['SAP.DE'] = (80.0, 'EUR')

        check()

        assert push_ready == []

    def test_no_message_without_the_switch(self, user, fake_yahoo, push_ready):
        PushSubscription.query.one().price_moves = False
        db.session.commit()
        holding(user, 'SAP.DE', 1, 100.0)
        fake_yahoo.last_prices['SAP.DE'] = (80.0, 'EUR')

        check()

        assert push_ready == []

    def test_sent_message_survives_a_restart(self, user, fake_yahoo, push_ready):
        holding(user, 'SAP.DE', 1, 100.0)
        fake_yahoo.last_prices['SAP.DE'] = (80.0, 'EUR')
        check()
        alerts._state.update(snapshot=None, dirty=True)  # wie nach einem Neustart

        check()

        assert len(push_ready) == 1
        assert PushLog.query.count() == 1


class TestDepotMove:

    def test_single_position_gets_no_extra_depot_message(self, user, fake_yahoo, push_ready):
        holding(user, 'SAP.DE', 1, 100.0)
        fake_yahoo.last_prices['SAP.DE'] = (94.0, 'EUR')

        assert check()['depot'] == 0

    def test_depot_move_across_positions(self, user, fake_yahoo, push_ready):
        """Jede Position unter 5 %, zusammen aber mehr als 3 % im Plus"""
        holding(user, 'A.DE', 10, 100.0)
        holding(user, 'B.DE', 10, 100.0)
        fake_yahoo.last_prices['A.DE'] = (104.0, 'EUR')
        fake_yahoo.last_prices['B.DE'] = (103.0, 'EUR')

        summary = check()

        assert summary['depot'] == 1 and summary['moves'] == 0
        assert push_ready[0]['title'] == 'Dein Depot heute deutlich im Plus'
        assert '€' not in push_ready[0]['body']


class TestWatchlistTargets:

    def watch(self, user, target=110.0, direction='above'):
        asset = Asset(name='SAP SE', symbol='SAP.DE', currency='EUR', asset_type='stock')
        db.session.add(asset)
        db.session.commit()
        item = Watchlist(user_id=user.id, asset_id=asset.id, price_added=100,
                         target_price=target, target_direction=direction)
        db.session.add(item)
        db.session.commit()
        return item

    def test_target_reached_once(self, user, fake_yahoo, push_ready):
        item = self.watch(user)
        fake_yahoo.last_prices['SAP.DE'] = (109.0, 'EUR')
        check()
        assert push_ready == []

        fake_yahoo.last_prices['SAP.DE'] = (110.5, 'EUR')
        assert check()['targets'] == 1
        check()

        assert [m['title'] for m in push_ready] == ['SAP SE: Zielkurs erreicht']
        assert push_ready[0]['body'] == 'Der Kurs ist über deinen Zielkurs gestiegen.'
        assert db.session.get(Watchlist, item.id).target_hit_at is not None

    def test_target_from_above(self, user, fake_yahoo, push_ready):
        self.watch(user, target=90.0, direction='below')
        fake_yahoo.last_prices['SAP.DE'] = (89.0, 'EUR')

        check()

        assert push_ready[0]['body'] == 'Der Kurs ist unter deinen Zielkurs gefallen.'


class TestQuietAndCheap:

    def test_quiet_hours(self, user, fake_yahoo, push_ready):
        holding(user, 'SAP.DE', 1, 100.0)
        fake_yahoo.last_prices['SAP.DE'] = (80.0, 'EUR')

        assert check(now=datetime(2026, 11, 12, 22, 0)) == {'push': 'Ruhezeit'}
        assert check(now=datetime(2026, 11, 12, 7, 59)) == {'push': 'Ruhezeit'}
        assert push_ready == []

    def test_check_without_hits_does_not_touch_the_database(self, app, user, fake_yahoo):
        """Nach dem ersten Aufbau fragt eine ruhige Prüfung nur yfinance, nicht Neon"""
        holding(user, 'SAP.DE', 1, 100.0)
        fake_yahoo.last_prices['SAP.DE'] = (101.0, 'EUR')
        check()  # baut den Zwischenspeicher

        statements = []
        listener = lambda *args: statements.append(args[2])
        event.listen(db.engine, 'before_cursor_execute', listener)
        try:
            check()
            check()
        finally:
            event.remove(db.engine, 'before_cursor_execute', listener)

        assert statements == []

    def test_changes_rebuild_the_snapshot(self, user, fake_yahoo, push_ready):
        check()
        assert alerts._state['dirty'] is False

        holding(user, 'SAP.DE', 1, 100.0)  # neue Position

        assert alerts._state['dirty'] is True
        fake_yahoo.last_prices['SAP.DE'] = (80.0, 'EUR')
        assert check()['moves'] == 1


class TestTargetRoute:

    @pytest.fixture
    def client(self, user, login_client, monkeypatch):
        monkeypatch.setattr('fintrack.portfolio.routes.get_current_price', lambda asset, **kw: 100.0)
        return login_client('a@test.com')

    def test_direction_follows_current_price(self, client):
        asset = Asset(name='SAP SE', symbol='SAP.DE', currency='EUR', asset_type='stock')
        db.session.add(asset)
        db.session.commit()
        client.post('/api/v1/me/watchlist', json={'asset_id': asset.id})

        up = client.put(f'/api/v1/me/watchlist/{asset.id}/target', json={'target_price': 120})
        assert up.get_json() == {'target_price': 120, 'target_direction': 'above'}
        down = client.put(f'/api/v1/me/watchlist/{asset.id}/target', json={'target_price': 80})
        assert down.get_json()['target_direction'] == 'below'

        item = client.get('/api/v1/me/watchlist').get_json()[0]
        assert (item['target_price'], item['target_direction'], item['target_hit']) == (80, 'below', None)

        cleared = client.put(f'/api/v1/me/watchlist/{asset.id}/target', json={'target_price': None})
        assert cleared.get_json() == {'target_price': None, 'target_direction': None}

    def test_new_target_resets_hit(self, client, user):
        asset = Asset(name='SAP SE', symbol='SAP.DE', currency='EUR', asset_type='stock')
        db.session.add(asset)
        db.session.commit()
        db.session.add(Watchlist(user_id=user.id, asset_id=asset.id, target_price=90, target_direction='below',
                                 target_hit_at=datetime(2026, 11, 1)))
        db.session.commit()

        client.put(f'/api/v1/me/watchlist/{asset.id}/target', json={'target_price': 130})

        assert Watchlist.query.one().target_hit_at is None

    def test_rejects_unknown_item_and_current_price(self, client):
        assert client.put('/api/v1/me/watchlist/999/target', json={'target_price': 120}).status_code == 404

        asset = Asset(name='SAP SE', symbol='SAP.DE', currency='EUR', asset_type='stock')
        db.session.add(asset)
        db.session.commit()
        client.post('/api/v1/me/watchlist', json={'asset_id': asset.id})
        assert client.put(f'/api/v1/me/watchlist/{asset.id}/target', json={'target_price': 100}).status_code == 400
