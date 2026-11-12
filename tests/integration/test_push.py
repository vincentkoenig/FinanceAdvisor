"""
test_push.py - Push-Benachrichtigungen: Geräte an- und abmelden (/api/v1/me/push),
Versand mit Aufräumen abgelaufener Abos (push/service.py) und die Meldungen des
Morgen-Laufs (push/notify.py). Der echte Versand an Google/Apple ist ersetzt.
"""

import sys
import os
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.extensions import db
from fintrack.models import Asset, Contract, DailyInsight, PushLog, PushSubscription, SavingsPlan
from fintrack.push import notify, service

ENDPOINT = 'https://push.example.com/geraet-1'
DEVICE = {'endpoint': ENDPOINT, 'keys': {'p256dh': 'BPub', 'auth': 'geheim'}}


@pytest.fixture(autouse=True)
def push_ready(monkeypatch):
    """VAPID-Schlüssel gesetzt, Versand landet in einer Liste statt beim Push-Dienst."""
    public, private = service.generate_vapid_keys()
    monkeypatch.setenv('VAPID_PUBLIC_KEY', public)
    monkeypatch.setenv('VAPID_PRIVATE_KEY', private)
    delivered = []
    status = {'code': 201}

    def deliver(subscription, payload, private_key):
        delivered.append((subscription.endpoint, payload))
        return status['code']

    monkeypatch.setattr(service, '_deliver', deliver)
    return {'delivered': delivered, 'status': status}


@pytest.fixture
def client(make_user, login_client):
    make_user('a@test.com')
    return login_client('a@test.com')


def subscribe(client, **changes):
    response = client.post('/api/v1/me/push/devices', json={**DEVICE, **changes})
    assert response.status_code == 200, response.get_json()
    return response.get_json()


class TestDevices:

    def test_config_offers_public_key(self, client):
        data = client.get('/api/v1/me/push').get_json()

        assert data['available'] is True
        assert data['public_key'] == os.environ['VAPID_PUBLIC_KEY']

    def test_without_keys_push_is_not_available(self, client, monkeypatch):
        monkeypatch.delenv('VAPID_PRIVATE_KEY')

        assert client.get('/api/v1/me/push').get_json() == {'available': False, 'public_key': None}
        assert client.post('/api/v1/me/push/devices', json=DEVICE).status_code == 503

    def test_subscribe_read_and_change(self, client):
        assert subscribe(client) == {'deadlines': True, 'savings_plan': True, 'daily_update': True}

        response = client.post('/api/v1/me/push/devices/current', json={'endpoint': ENDPOINT, 'daily_update': False})
        assert response.get_json() == {'deadlines': True, 'savings_plan': True, 'daily_update': False}
        assert client.post('/api/v1/me/push/devices/current', json={'endpoint': ENDPOINT}).get_json() == \
            {'deadlines': True, 'savings_plan': True, 'daily_update': False}

    def test_subscribing_again_updates_the_same_device(self, client):
        subscribe(client)
        subscribe(client, keys={'p256dh': 'BNeu', 'auth': 'neu'})

        assert PushSubscription.query.one().p256dh == 'BNeu'

    def test_device_moves_to_the_account_logged_in_now(self, make_user, login_client):
        make_user('a@test.com')
        second = make_user('b@test.com')
        subscribe(login_client('a@test.com'))
        subscribe(login_client('b@test.com'))

        assert PushSubscription.query.one().user_id == second.id

    def test_other_users_device_is_not_visible(self, make_user, login_client):
        make_user('a@test.com')
        make_user('b@test.com')
        subscribe(login_client('a@test.com'))

        other = login_client('b@test.com')
        assert other.post('/api/v1/me/push/devices/current', json={'endpoint': ENDPOINT}).status_code == 404
        assert other.post('/api/v1/me/push/test', json={'endpoint': ENDPOINT}).status_code == 404

    def test_only_https_endpoints(self, client):
        response = client.post('/api/v1/me/push/devices', json={**DEVICE, 'endpoint': 'http://intern:8000/x'})

        assert response.status_code == 400

    def test_remove(self, client):
        subscribe(client)

        assert client.post('/api/v1/me/push/devices/remove', json={'endpoint': ENDPOINT}).status_code == 200
        assert PushSubscription.query.count() == 0

    def test_test_message(self, client, push_ready):
        subscribe(client)

        assert client.post('/api/v1/me/push/test', json={'endpoint': ENDPOINT}).status_code == 200
        assert push_ready['delivered'][0][1]['title'] == 'FinTrack'

    def test_needs_login(self, app):
        assert app.test_client().get('/api/v1/me/push').status_code == 401


class TestSending:

    def test_expired_subscription_is_removed(self, client, push_ready):
        subscribe(client)
        push_ready['status']['code'] = 410

        assert client.post('/api/v1/me/push/test', json={'endpoint': ENDPOINT}).status_code == 502
        assert PushSubscription.query.count() == 0

    def test_topic_switch_is_respected(self, client, push_ready):
        subscribe(client, daily_update=False)
        user_id = PushSubscription.query.one().user_id

        assert service.send_to_user(user_id, 'daily_update', 'T', 'B') == 0
        assert service.send_to_user(user_id, 'deadlines', 'T', 'B') == 1


TODAY = date(2026, 9, 16)  # 14 Tage vor dem letzten Kündigungstag 30.09.


def add_contract(user_id, **changes):
    values = dict(user_id=user_id, name='Haftpflicht', category='insurance', amount=60, interval='yearly',
                  start_date=date(2024, 1, 1), renewal_months=12, notice_value=3, notice_unit='months')
    values.update(changes)
    contract = Contract(**values)
    db.session.add(contract)
    db.session.commit()
    return contract


class TestMorningRun:

    @pytest.fixture
    def user_id(self, client):
        subscribe(client)
        return PushSubscription.query.one().user_id

    def test_deadline_reminders_at_14_and_3_days(self, user_id, push_ready):
        add_contract(user_id)

        notify.notify_all_users(today=TODAY - timedelta(days=1))
        assert push_ready['delivered'] == []  # noch 15 Tage

        assert notify.notify_all_users(today=TODAY)['deadlines'] == 1
        notify.notify_all_users(today=TODAY + timedelta(days=1))  # schon erinnert
        assert len(push_ready['delivered']) == 1
        message = push_ready['delivered'][0][1]
        assert message['title'] == 'Kündigungsfrist: Haftpflicht'
        assert message['body'] == 'Noch 14 Tage zum Kündigen, bis 30.09.2026.'
        assert message['url'] == '/app/contracts'

        notify.notify_all_users(today=date(2026, 9, 27))
        assert push_ready['delivered'][-1][1]['body'] == 'Noch 3 Tage zum Kündigen, bis 30.09.2026.'
        assert len(push_ready['delivered']) == 2

    def test_missed_run_sends_only_the_closest_reminder(self, user_id, push_ready):
        add_contract(user_id)

        notify.notify_all_users(today=date(2026, 9, 29))

        assert [m[1]['body'] for m in push_ready['delivered']] == ['Morgen ist der letzte Tag zum Kündigen (30.09.2026).']
        notify.notify_all_users(today=date(2026, 9, 30))
        assert len(push_ready['delivered']) == 1

    def test_cancelled_contract_gets_no_reminder(self, user_id, push_ready):
        add_contract(user_id, cancelled_at=date(2026, 9, 1), end_date=date(2026, 12, 31))

        notify.notify_all_users(today=TODAY)

        assert push_ready['delivered'] == []

    def test_savings_plan_due_once_until_confirmed(self, user_id, push_ready):
        asset = Asset(name='iShares Core MSCI World', symbol='EUNL.DE', currency='EUR', asset_type='etf')
        db.session.add(asset)
        db.session.commit()
        db.session.add(SavingsPlan(user_id=user_id, asset_id=asset.id, amount=200, day_of_month=15,
                                   last_executed=datetime(2026, 8, 15)))
        db.session.commit()

        notify.notify_all_users(today=TODAY, now=datetime(2026, 9, 14, 8, 0))
        assert push_ready['delivered'] == []  # erst am 15.

        assert notify.notify_all_users(today=TODAY, now=datetime(2026, 9, 15, 8, 0))['savings_plan'] == 1
        notify.notify_all_users(today=TODAY, now=datetime(2026, 9, 16, 8, 0))
        assert len(push_ready['delivered']) == 1
        message = push_ready['delivered'][0][1]
        assert message['title'] == 'Sparplan fällig: iShares Core MSCI World'
        assert '200' not in message['body']

    def test_executed_savings_plan_is_not_announced(self, user_id, push_ready):
        db.session.add(SavingsPlan(user_id=user_id, asset_id=None, amount=50, day_of_month=1,
                                   last_executed=datetime(2026, 9, 1, 9, 0)))
        db.session.commit()

        notify.notify_all_users(today=TODAY, now=datetime(2026, 9, 2, 8, 0))

        assert push_ready['delivered'] == []

    def test_daily_update_once_without_content(self, user_id, push_ready):
        now = datetime(2026, 9, 16, 8, 0)
        db.session.add(DailyInsight(user_id=user_id, content='Dein Depot liegt bei 15.800 €.',
                                    created_at=datetime(2026, 9, 15, 22, 35)))
        db.session.commit()

        assert notify.notify_all_users(today=TODAY, now=now)['daily_update'] == 1
        notify.notify_all_users(today=TODAY, now=now)

        assert len(push_ready['delivered']) == 1
        assert '€' not in push_ready['delivered'][0][1]['body']
        assert PushLog.query.count() == 1

    def test_old_insight_is_not_announced(self, user_id, push_ready):
        db.session.add(DailyInsight(user_id=user_id, content='alt', created_at=datetime(2026, 9, 10, 22, 35)))
        db.session.commit()

        notify.notify_all_users(today=TODAY, now=datetime(2026, 9, 16, 8, 0))

        assert push_ready['delivered'] == []

    def test_without_keys_nothing_happens(self, user_id, monkeypatch, push_ready):
        add_contract(user_id)
        monkeypatch.delenv('VAPID_PUBLIC_KEY')

        assert notify.notify_all_users(today=TODAY) == {'push': 'nicht eingerichtet'}
        assert push_ready['delivered'] == []


def test_generated_keys_work_with_pywebpush():
    """Das erzeugte Schlüsselpaar passt zueinander, so wie pywebpush es liest"""
    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid
    import base64

    public, private = service.generate_vapid_keys()
    derived = Vapid.from_string(private).public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    assert base64.urlsafe_b64encode(derived).rstrip(b'=').decode() == public
