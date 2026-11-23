"""
test_savings_goals.py - Sparziele als Töpfe vom Kontostand (goals/): Stand mit Rate,
Plan bis zum Zieldatum, Ein- und Auszahlungen, Vergleich mit dem Kontostand, Push und Export.
"""

import json
from datetime import date

import pytest

from fintrack.extensions import db
from fintrack.goals import service
from fintrack.models import AccountBalance, PushLog, PushSubscription, SavingsGoal, SavingsGoalEntry, User

TODAY = date(2026, 11, 23)


@pytest.fixture
def user(make_user, monkeypatch):
    monkeypatch.setattr(service, 'today_berlin', lambda: TODAY)
    return make_user('a@test.com')


def goal(user, target=1000, rate=None, rate_since=None, target_date=None, entries=()):
    g = SavingsGoal(user_id=user.id, name='Urlaub', target_amount=target, monthly_amount=rate,
                    rate_since=rate_since, target_date=target_date)
    db.session.add(g)
    db.session.flush()
    for amount in entries:
        db.session.add(SavingsGoalEntry(goal_id=g.id, user_id=user.id, date=TODAY, amount=amount))
    db.session.commit()
    return g


class TestBalance:

    def test_rate_counts_once_per_started_month(self, app, user):
        g = goal(user, rate=100, rate_since=date(2026, 9, 1), entries=[50])

        assert service.balance(g, TODAY) == 350  # 50 + September, Oktober, November

    def test_rate_stops_at_the_target(self, app, user):
        g = goal(user, target=500, rate=200, rate_since=date(2026, 1, 1), entries=[100])

        assert service.balance(g, TODAY) == 500

    def test_plan_with_target_date(self, app, user):
        behind = service.describe(goal(user, target=1300, rate=100, rate_since=date(2026, 11, 1),
                                       target_date=date(2027, 5, 15)), TODAY)
        on_track = service.describe(goal(user, target=1300, rate=200, rate_since=date(2026, 11, 1),
                                         target_date=date(2027, 5, 15)), TODAY)

        # 1.200 € fehlen (100 € im November), 6 Monate bis Mai -> 200 € pro Monat nötig
        assert behind['plan'] == {'status': 'behind', 'needed_monthly': 200.0, 'months_left': 6, 'shortfall_monthly': 100.0}
        assert on_track['plan']['status'] == 'on_track'

    def test_past_date_is_overdue(self, app, user):
        assert service.describe(goal(user, target_date=date(2026, 10, 1)), TODAY)['plan']['status'] == 'overdue'


class TestChanges:

    def test_changing_the_rate_keeps_what_was_saved(self, app, user, login_client):
        g = goal(user, target=5000, rate=100, rate_since=date(2026, 9, 1))
        client = login_client('a@test.com')

        response = client.put(f'/api/v1/me/goals/{g.id}', json={'name': 'Urlaub', 'target_amount': 5000, 'monthly_amount': 300})

        assert response.status_code == 200 and response.get_json()['goal']['balance'] == 300
        # Die neue Rate kommt erst im Dezember dazu
        assert service.balance(db.session.get(SavingsGoal, g.id), date(2026, 12, 2)) == 600

    def test_withdrawal_is_limited_and_does_not_refill(self, app, user, login_client):
        g = goal(user, target=1000, rate=100, rate_since=date(2026, 11, 1), entries=[200])
        client = login_client('a@test.com')

        too_much = client.post(f'/api/v1/me/goals/{g.id}/entries', json={'amount': -400})
        ok = client.post(f'/api/v1/me/goals/{g.id}/entries', json={'amount': -250, 'note': 'Flug'})

        assert too_much.status_code == 400 and 'nur 300,00 €' in too_much.get_json()['error']
        assert ok.status_code == 201 and ok.get_json()['goal']['balance'] == 50
        # Kein Nachfüllen durch die Rate im selben Monat
        assert service.balance(db.session.get(SavingsGoal, g.id), TODAY) == 50

    def test_create_with_start_amount_and_rate(self, app, user, login_client):
        response = login_client('a@test.com').post('/api/v1/me/goals', json={
            'name': 'Notgroschen', 'target_amount': 10000, 'monthly_amount': 250, 'start_amount': 2000,
            'target_date': ''})

        assert response.status_code == 201
        body = response.get_json()['goal']
        assert body['balance'] == 2250 and body['target_date'] is None and body['plan'] is None

    def test_other_users_goal_is_not_found(self, app, user, make_user, login_client):
        g = goal(user)
        make_user('b@test.com')

        assert login_client('b@test.com').post(f'/api/v1/me/goals/{g.id}/entries', json={'amount': 5}).status_code == 404


class TestOverview:

    def test_warns_when_pots_exceed_the_account(self, app, user, login_client):
        goal(user, entries=[800])
        goal(user, entries=[500])
        db.session.add(AccountBalance(user_id=user.id, date=TODAY, amount=1000))
        db.session.commit()

        body = login_client('a@test.com').get('/api/v1/me/goals').get_json()

        assert body['total'] == 1300 and body['cash_balance'] == 1000 and body['over_by'] == 300


class TestPushAndExport:

    def test_reached_goal_is_announced_once(self, app, user, monkeypatch):
        from fintrack.push import notify
        from fintrack.push import service as push_service
        public, private = push_service.generate_vapid_keys()
        monkeypatch.setenv('VAPID_PUBLIC_KEY', public)
        monkeypatch.setenv('VAPID_PRIVATE_KEY', private)
        sent = []
        monkeypatch.setattr(push_service, '_deliver', lambda sub, payload, key: sent.append(payload) or 201)
        db.session.add(PushSubscription(user_id=user.id, endpoint='https://push.example/1', p256dh='k', auth='a'))
        goal(user, target=300, rate=100, rate_since=date(2026, 9, 1))  # durch die Rate voll

        assert notify.notify_goals(user.id, TODAY) == 1
        assert notify.notify_goals(user.id, TODAY) == 0
        assert sent[0]['title'] == 'Sparziel erreicht: Urlaub' and PushLog.query.count() == 1

    def test_goals_survive_export_and_import(self, app, user, make_user, login_client, mocker):
        mocker.patch('fintrack.account.routes.prepare_new_asset', return_value=0)
        goal(user, target=900, rate=50, rate_since=date(2026, 10, 1), target_date=date(2027, 6, 1), entries=[120])
        export = json.loads(login_client('a@test.com').get('/api/v1/me/export').data)
        make_user('b@test.com')

        response = login_client('b@test.com').post('/api/v1/me/import', json=export)

        assert response.status_code == 201
        other = User.query.filter_by(email='b@test.com').one()
        copied = SavingsGoal.query.filter_by(user_id=other.id).one()
        assert (copied.target_amount, copied.monthly_amount, copied.target_date) == (900, 50, date(2027, 6, 1))
        assert service.balance(copied, TODAY) == 220
