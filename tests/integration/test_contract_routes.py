"""
test_contract_routes.py - Tests für die Verträge-API unter /api/v1/me/contracts:
anlegen, prüfen, bearbeiten, kündigen, Kündigung zurücknehmen, löschen und
die Übersicht mit Summen.
"""

import sys
import os
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest

from fintrack.extensions import db
from fintrack.models import Contract

TODAY = date(2026, 8, 1)

INSURANCE = {
    'name': 'Haftpflicht', 'provider': 'Beispiel Versicherung', 'category': 'insurance',
    'amount': 60, 'interval': 'yearly', 'start_date': '2024-01-01',
    'renewal_months': 12, 'notice_value': 3, 'notice_unit': 'months',
}


@pytest.fixture(autouse=True)
def fixed_today(mocker):
    """Fristen hängen vom heutigen Tag ab - in den Tests ist immer der 01.08.2026."""
    mocker.patch('fintrack.contracts.routes.today_berlin', return_value=TODAY)
    mocker.patch('fintrack.contracts.service.today_berlin', return_value=TODAY)


@pytest.fixture
def client(make_user, login_client):
    make_user('a@test.com')
    return login_client('a@test.com')


def create(client, **changes):
    response = client.post('/api/v1/me/contracts', json={**INSURANCE, **changes})
    assert response.status_code == 201, response.get_json()
    return response.get_json()['contract']


class TestCreate:

    def test_created_contract_has_deadlines(self, client):
        contract = create(client)

        assert contract['status'] == 'active'
        assert contract['cancel_by'] == '2026-09-30'
        assert contract['cancel_effective'] == '2026-12-31'
        assert contract['days_to_cancel'] == 60
        assert contract['yearly_cost'] == 60
        assert contract['monthly_cost'] == 5
        assert contract['min_term_end'] is None

    def test_minimum_term_end_is_reported(self, client):
        contract = create(client, category='telecom', start_date='2025-03-15', min_term_months=24, renewal_months=1)

        assert contract['min_term_end'] == '2027-03-14'

    def test_empty_optional_texts_are_stored_as_null(self, client):
        contract = create(client, provider='  ', notes='')

        assert contract['provider'] is None and contract['notes'] is None

    @pytest.mark.parametrize('changes,field', [
        ({'amount': 0}, 'amount'),
        ({'category': 'auto'}, 'category'),
        ({'interval': 'weekly'}, 'interval'),
        ({'notice_unit': 'years'}, 'notice_unit'),
        ({'start_date': '01.01.2026'}, 'start_date'),
        ({'name': ''}, 'name'),
    ])
    def test_invalid_input_is_rejected(self, client, changes, field):
        response = client.post('/api/v1/me/contracts', json={**INSURANCE, **changes})

        assert response.status_code == 400
        assert field in response.get_json()['fields']
        assert Contract.query.count() == 0

    def test_needs_some_term(self, client):
        response = client.post('/api/v1/me/contracts', json={**INSURANCE, 'renewal_months': None})

        assert response.status_code == 400
        assert 'Mindestlaufzeit oder Verlängerung' in response.get_json()['error']


class TestOverview:

    def test_sorted_by_deadline_with_totals_of_running_contracts(self, client):
        create(client, name='Strom', category='energy', amount=80, interval='monthly',
               start_date='2026-01-01', renewal_months=1, notice_value=1)
        create(client)
        create(client, name='Alter Kredit', category='loan', amount=100, interval='monthly',
               start_date='2020-01-01', min_term_months=24, renewal_months=None)

        data = client.get('/api/v1/me/contracts').get_json()

        assert [c['name'] for c in data['contracts']] == ['Strom', 'Haftpflicht', 'Alter Kredit']
        assert data['contracts'][2]['status'] == 'ended'
        # Beendete Verträge zählen nicht mehr mit
        assert data['yearly_total'] == 80 * 12 + 60
        assert data['monthly_total'] == 85


class TestUpdateAndDelete:

    def test_update_replaces_fields(self, client):
        contract = create(client)

        response = client.put(f"/api/v1/me/contracts/{contract['id']}",
                              json={**INSURANCE, 'amount': 72, 'notice_value': 1})

        assert response.status_code == 200
        updated = response.get_json()['contract']
        assert updated['amount'] == 72
        assert updated['cancel_by'] == '2026-11-30'

    def test_delete(self, client):
        contract = create(client)

        assert client.delete(f"/api/v1/me/contracts/{contract['id']}").status_code == 200
        assert Contract.query.count() == 0

    def test_unknown_contract_is_404(self, client):
        assert client.put('/api/v1/me/contracts/999', json=INSURANCE).status_code == 404


class TestCancel:

    def test_cancel_ends_at_next_possible_date(self, client):
        contract = create(client)

        response = client.post(f"/api/v1/me/contracts/{contract['id']}/cancel", json={})

        cancelled = response.get_json()['contract']
        assert response.status_code == 200
        assert cancelled['status'] == 'cancelled'
        assert cancelled['cancelled_at'] == '2026-08-01'
        assert cancelled['end_date'] == '2026-12-31'
        assert cancelled['cancel_by'] is None

    def test_cancel_with_own_end_date(self, client):
        contract = create(client)

        response = client.post(f"/api/v1/me/contracts/{contract['id']}/cancel", json={'end_date': '2026-10-31'})

        assert response.get_json()['contract']['end_date'] == '2026-10-31'

    def test_cannot_cancel_twice(self, client):
        contract = create(client)
        client.post(f"/api/v1/me/contracts/{contract['id']}/cancel", json={})

        response = client.post(f"/api/v1/me/contracts/{contract['id']}/cancel", json={})

        assert response.status_code == 409

    def test_end_date_before_start_is_rejected(self, client):
        contract = create(client)

        response = client.post(f"/api/v1/me/contracts/{contract['id']}/cancel", json={'end_date': '2023-12-31'})

        assert response.status_code == 400
        assert db.session.get(Contract, contract['id']).end_date is None

    def test_undo_cancel(self, client):
        contract = create(client)
        client.post(f"/api/v1/me/contracts/{contract['id']}/cancel", json={})

        response = client.delete(f"/api/v1/me/contracts/{contract['id']}/cancel")

        restored = response.get_json()['contract']
        assert restored['status'] == 'active'
        assert restored['end_date'] is None and restored['cancelled_at'] is None
        assert restored['cancel_by'] == '2026-09-30'

    def test_editing_keeps_the_cancellation(self, client):
        contract = create(client)
        client.post(f"/api/v1/me/contracts/{contract['id']}/cancel", json={})

        updated = client.put(f"/api/v1/me/contracts/{contract['id']}",
                             json={**INSURANCE, 'amount': 99}).get_json()['contract']

        assert updated['status'] == 'cancelled'
        assert updated['end_date'] == '2026-12-31'


class TestChatTool:

    def test_chat_can_read_contracts(self, client, mocker):
        """Fragt das Sprachmodell nach get_contracts, bekommt es die eigenen Verträge mit Fristen"""
        from types import SimpleNamespace

        create(client)
        tool_call = SimpleNamespace(id='call_1', function=SimpleNamespace(name='get_contracts', arguments='{}'))
        first = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=[tool_call], content=None))])
        second = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Bis 30.09. kündigen'))])
        fake_client = mocker.Mock()
        fake_client.chat.completions.create.side_effect = [first, second]
        mocker.patch('fintrack.chat.routes.get_openai_client', return_value=fake_client)

        response = client.post('/api/v1/me/chat', json={'message': 'Wann kann ich die Haftpflicht kündigen?'})

        assert response.status_code == 200
        tool_answer = fake_client.chat.completions.create.call_args_list[1].kwargs['messages'][-1]
        assert tool_answer['role'] == 'tool'
        assert 'Haftpflicht' in tool_answer['content'] and '2026-09-30' in tool_answer['content']


class TestBooking:
    """Verknüpfung mit dem Haushaltsbuch"""

    @pytest.fixture
    def categories(self, client):
        from fintrack.models import Category, User
        user = User.query.filter_by(email='a@test.com').one()
        fixed = Category(user_id=user.id, name='Versicherungen', type='fixed_expense')
        variable = Category(user_id=user.id, name='Freizeit', type='variable_expense')
        db.session.add_all([fixed, variable])
        db.session.commit()
        return fixed, variable

    def booking_of(self, contract):
        from fintrack.models import Transaction
        return db.session.get(Transaction, db.session.get(Contract, contract['id']).transaction_id)

    def test_new_booking_is_monthly_share_from_this_month(self, client, categories):
        """Jährlich 60 € werden als 5 € pro Monat gebucht, ab dem laufenden Monat statt rückwirkend ab 2024"""
        contract = create(client)

        response = client.post(f"/api/v1/me/contracts/{contract['id']}/booking", json={'category_id': categories[0].id})

        assert response.status_code == 200
        assert response.get_json()['contract']['booking'] == {
            'id': self.booking_of(contract).id, 'amount': 5.0, 'category_name': 'Versicherungen', 'end_date': None}
        booking = self.booking_of(contract)
        assert booking.is_recurring and booking.description == 'Haftpflicht'
        assert booking.date.date() == date(2026, 8, 1)

    def test_fixed_term_booking_ends_with_contract(self, client, categories):
        loan = create(client, name='Kredit', category='loan', amount=100, interval='monthly',
                      start_date='2026-09-15', min_term_months=12, renewal_months=None)

        client.post(f"/api/v1/me/contracts/{loan['id']}/booking", json={'category_id': categories[0].id})

        booking = self.booking_of(loan)
        assert booking.date.date() == date(2026, 9, 15)
        assert booking.end_date.date() == date(2027, 9, 14)

    def test_cancel_and_undo_move_the_booking_end(self, client, categories):
        contract = create(client)
        client.post(f"/api/v1/me/contracts/{contract['id']}/booking", json={'category_id': categories[0].id})

        client.post(f"/api/v1/me/contracts/{contract['id']}/cancel", json={})
        assert self.booking_of(contract).end_date.date() == date(2026, 12, 31)

        client.delete(f"/api/v1/me/contracts/{contract['id']}/cancel")
        assert self.booking_of(contract).end_date is None

    def test_link_existing_recurring_booking(self, client, categories):
        from fintrack.models import Transaction, User
        user = User.query.filter_by(email='a@test.com').one()
        existing = Transaction(user_id=user.id, category_id=categories[0].id, amount=5, description='Haftpflicht',
                               date=datetime(2025, 1, 1), is_recurring=True)
        db.session.add(existing)
        db.session.commit()
        contract = create(client)
        client.post(f"/api/v1/me/contracts/{contract['id']}/cancel", json={})

        response = client.post(f"/api/v1/me/contracts/{contract['id']}/booking", json={'transaction_id': existing.id})

        assert response.status_code == 200
        db.session.expire_all()
        linked = db.session.get(Transaction, existing.id)
        # Übernommen samt Vertragsende, Startdatum und Betrag bleiben
        assert linked.end_date.date() == date(2026, 12, 31)
        assert linked.date == datetime(2025, 1, 1) and linked.amount == 5

    @pytest.mark.parametrize('kind,status,message', [
        ('variable', 400, 'Fixkosten-Kategorie'),
        ('one_time', 400, 'Nur wiederkehrende'),
        ('both', 400, 'Entweder'),
    ])
    def test_rejects_wrong_targets(self, client, categories, kind, status, message):
        from fintrack.models import Transaction, User
        user = User.query.filter_by(email='a@test.com').one()
        one_time = Transaction(user_id=user.id, category_id=categories[0].id, amount=5, date=datetime(2026, 1, 1))
        db.session.add(one_time)
        db.session.commit()
        body = {'variable': {'category_id': categories[1].id}, 'one_time': {'transaction_id': one_time.id},
                'both': {'category_id': categories[0].id, 'transaction_id': one_time.id}}[kind]
        contract = create(client)

        response = client.post(f"/api/v1/me/contracts/{contract['id']}/booking", json=body)

        assert response.status_code == status
        assert message in response.get_json()['error']
        assert db.session.get(Contract, contract['id']).transaction_id is None

    def test_one_booking_per_contract(self, client, categories):
        first = create(client)
        second = create(client, name='Hausrat')
        client.post(f"/api/v1/me/contracts/{first['id']}/booking", json={'category_id': categories[0].id})
        booking_id = self.booking_of(first).id

        assert client.post(f"/api/v1/me/contracts/{first['id']}/booking",
                           json={'category_id': categories[0].id}).status_code == 409
        assert client.post(f"/api/v1/me/contracts/{second['id']}/booking",
                           json={'transaction_id': booking_id}).status_code == 409

    def test_unlink_keeps_booking(self, client, categories):
        from fintrack.models import Transaction
        contract = create(client)
        client.post(f"/api/v1/me/contracts/{contract['id']}/booking", json={'category_id': categories[0].id})
        booking_id = self.booking_of(contract).id

        response = client.delete(f"/api/v1/me/contracts/{contract['id']}/booking")

        assert response.get_json()['contract']['booking'] is None
        assert db.session.get(Transaction, booking_id) is not None

    def test_deleting_the_booking_keeps_the_contract(self, client, categories):
        contract = create(client)
        client.post(f"/api/v1/me/contracts/{contract['id']}/booking", json={'category_id': categories[0].id})
        booking_id = self.booking_of(contract).id

        assert client.delete(f'/api/v1/me/transactions/{booking_id}').status_code == 200

        db.session.expire_all()
        assert db.session.get(Contract, contract['id']).transaction_id is None
        assert client.get('/api/v1/me/contracts').get_json()['contracts'][0]['booking'] is None
